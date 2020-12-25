"""
Webhook API from Typeform
"""
import json
import boto3
from io import BytesIO

from constants import SCALING_FACTOR, LEVEL_WEIGHTS, METRICS

with open('interpreter_schema.json', 'r') as schema:
    SCHEMA = json.loads(schema.read())

with open('score_scale.json', 'r') as scores:
    SCORES = json.loads(schema.read())


class ScoreComputation:

    def __init__(self):
        self.scores = {
            metric: 0 for metric in METRICS
        }

        self.scaled_scores = {}
        self.overall_score = 0

    def _add_answer(self, answer_level: int, answer_id: str):
        """
        Populate an answer and calculate the corresponding scores
        :param answer_level: integer from 0 to 5
        :param answer_id: field ID from typeform
        """
        answer_weights = SCHEMA[answer_id]['weights']
        for metric_index, metric in enumerate(METRICS):
            self.scores[metric] += SCALING_FACTOR * LEVEL_WEIGHTS[answer_level] * answer_weights[metric_index]

    def aggregate_form_answers(self, payload: dict):
        """
        Aggregate form answers from payload and populate scores dictionary
        :param payload: Lambda payload from typeform
        """
        answers = payload['form_response']['answers']
        for answer in answers:
            field_id = answer['field']['id']
            if field_id in SCHEMA:
                self._add_answer(answer_level=SCHEMA[field_id]['option_vals'].index(answer['choice']['label']),
                                 answer_id=field_id)

    def compute_scaled_scores(self):
        """
        Compute Scaled Scores for the aggregates measured
        :return: dictionary of scaled scores
        """
        for metric_idx, metric in enumerate(METRICS):
            self.scaled_scores[metric] = round(
                SCORES['metric'][metric_idx]['slope'] * self.scores[metric] + SCORES['metric'][metric_idx]['y0'], 2
            )  # use fitted line to compute the scaled score; truncate to two decimal places for readability
        self.overall_score = round(SCORES['overall']['slope'] * sum(self.scores.values()) + SCORES['overall']['y0'], 2)

    def generate_results_url(self, graph_buffer):
        """
        Generate the results URL

def lambda_handler(event, context):
    ~ bloo blah ~

