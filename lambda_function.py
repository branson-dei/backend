"""
Webhook API from Typeform
"""
import json
import os
from urllib.parse import urlencode

import boto3
from constants import SCALING_FACTOR, LEVEL_WEIGHTS, METRICS

with open('interpreter_schema.json', 'r') as schema:
    SCHEMA = json.loads(schema.read())

with open('score_scale.json', 'r') as scores:
    SCORES = json.loads(schema.read())

client = boto3.client('ses')


class ScoreComputation:

    def __init__(self):
        self.raw_scores = {
            metric: 0 for metric in METRICS
        }

        self.scaled_scores = {}
        self.email = None
        self.raw_overall_score = 0
        self.overall_score = 0

    def _add_answer(self, answer_level: int, answer_id: str):
        """
        Populate an answer and calculate the corresponding raw_scores
        :param answer_level: integer from 0 to 5
        :param answer_id: field ID from typeform
        """
        answer_weights = SCHEMA[answer_id]['weights']
        for metric_index, metric in enumerate(METRICS):
            self.raw_scores[metric] += SCALING_FACTOR * LEVEL_WEIGHTS[answer_level] * answer_weights[metric_index]

    def aggregate_form_answers(self, payload: dict):
        """
        Aggregate form answers from payload and populate raw_scores dictionary
        :param payload: Lambda payload from typeform
        """
        answers = payload['form_response']['answers']
        for answer in answers:
            field_id = answer['field']['id']
            if answer['field']['type'] == 'email':
                self.email = answer['email']

            if field_id in SCHEMA['esat']:
                self._add_answer(answer_level=SCHEMA[field_id]['option_vals'].index(answer['choice']['label']),
                                 answer_id=field_id)
        if not self.email:
            raise Exception("Could not locate the email of the submitter!")

    def compute_scaled_scores(self):
        """
        Compute Scaled Scores for the aggregates measured
        :return: dictionary of scaled raw_scores
        """
        for metric_idx, metric in enumerate(METRICS):
            self.scaled_scores[metric] = round(
                SCORES['metric'][metric_idx]['slope'] * self.raw_scores[metric] + SCORES['metric'][metric_idx]['y0'], 2
            )  # use fitted line to compute the scaled score; truncate to two decimal places for readability

        self.raw_overall_score = sum(self.raw_scores.values())
        self.overall_score = round(
            SCORES['overall']['slope'] * self.raw_overall_score + SCORES['overall']['y0'], 2
        )

    def generate_results_url(self):
        """
        Generate the results URL for the user to view their results
        """
        # ss=scaled scores array, rs=raw scores array, o=overall score, ro=raw overall score
        parameters = {
            'o': self.overall_score, 'ro': self.raw_overall_score, 'ss': [], 'rs': []
        }

        for metric in METRICS:
            parameters['ss'].append(self.scaled_scores[metric])
            parameters['rs'].append(self.raw_scores[metric])

        return f"{os.environ['RESULTS_ROOT']}/?{urlencode(parameters)}"

    def send_email(self):
        """
        Send the Email via SES to alert the user that the score is ready
        """
        client.send_templated_email(
            Source='ESAT Assessment <results@esatassessment.org>',
            Destination={'ToAddresses': [self.email]},
            ReplyToAddresses=[os.environ['MAINTAINER_EMAIL']],
            Template='esat-result',
            TemplateData=f'{{"url":"{self.generate_results_url()}"}}'
        )


def lambda_handler(event, context):
    """
    Handle the TypeHook webhook
    :param event: API Gateway event
    :param context: Lambda Execution Context
    :return: Success or Failure
    """
    score_computer = ScoreComputation()
    score_computer.aggregate_form_answers(event['payload'])
    score_computer.compute_scaled_scores()
    score_computer.send_email()
    return {"success": "true"}
