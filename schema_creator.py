"""
Constants files for question weights
"""
import json
from typing import List

from typeform import Typeform

from constants import LEVEL_WEIGHTS, SCALING_FACTOR, SCORE_SCALE

# From Excel Sheet
QUESTION_WEIGHTS = [[6, 2, 2, 1, 1], [6, 2, 2, 1, 1], [6, 2, 2, 1, 1], [6, 4, 6, 4, 2], [6, 4, 4, 4, 2],
                    [1, 6, 6, 2, 1], [2, 6, 6, 1, 2], [2, 6, 6, 2, 1], [2, 6, 6, 2, 2], [1, 6, 6, 1, 1],
                    [2, 4, 6, 2, 2], [2, 6, 6, 4, 2], [1, 6, 6, 1, 1], [4, 6, 6, 4, 2], [4, 6, 6, 4, 2],
                    [2, 6, 4, 6, 2], [1, 4, 1, 6, 1], [2, 6, 4, 6, 1], [1, 2, 6, 6, 1], [2, 4, 2, 6, 1],
                    [2, 2, 4, 2, 6], [2, 2, 4, 2, 6], [1, 1, 1, 1, 6], [2, 4, 2, 1, 6], [2, 4, 2, 1, 6]]


class FormSchemaGenerator:
    def __init__(self, typeform_pat: str, form_id: str, question_weights: List[int], exclude_field_groups=(0,)):
        """
        :param typeform_pat: Personal Access Token from TypeForm API
        :param form_id: TypeForm Form ID
        :param question_weights: List of weights for each
        """
        self.api_client = Typeform(typeform_pat)
        self.form_id = form_id
        self.exclude_field_groups = exclude_field_groups
        self.question_weights = question_weights

    def compute_scale_equation_components(self, minimum, maximum):
        """
        Compute the components of a line and return in a dictionary.
        We use point slope form to calculate

        :param minimum: minimum value to scale to 1
        :param maximum: maximum value to scale to 10
        :return: {'slope': <slope>, 'y0': <y intercept>}
        """
        m_sec = (SCORE_SCALE[1] - SCORE_SCALE[0]) / (maximum - minimum)
        return {'slope': m_sec, 'y0': -1 * (m_sec * maximum) + SCORE_SCALE[1]}

    def generate_score_scale(self, target_file: str = None):
        """
        Generate the score scale for each category, so we can compute thresholds
        """
        score_scale = {'metric': [], 'overall': 0}

        metric_mins = [0.0, 0.0, 0.0, 0.0, 0.0]
        metric_maxes = [0.0, 0.0, 0.0, 0.0, 0.0]

        for question_weight in QUESTION_WEIGHTS:
            for metric_idx, metric in enumerate(question_weight):
                metric_mins[metric_idx] += LEVEL_WEIGHTS[0] * metric * SCALING_FACTOR
                metric_maxes[metric_idx] += LEVEL_WEIGHTS[-1] * metric * SCALING_FACTOR

        for metric_min, metric_max in zip(metric_mins, metric_maxes):  # fit a line between min and max to scale to 10
            score_scale['metric'].append(self.compute_scale_equation_components(minimum=metric_min, maximum=metric_max))

        score_scale['overall'] = self.compute_scale_equation_components(minimum=sum(metric_mins),
                                                                        maximum=sum(metric_maxes))

        if target_file:
            with open(target_file, 'w') as j_target:
                j_target.write(json.dumps(score_scale, indent=4))

        return score_scale

    def generate_schema(self, target_file: str = None):
        """
        Generate the json for the interpreter
        """
        interpreter_schema = {}
        schema = self.api_client.forms.get(self.form_id)
        question_id = 0

        for field_index, field_group in enumerate(schema['fields']):
            if field_index in self.exclude_field_groups:
                continue

            for field in field_group['properties']['fields']:
                if 'choices' not in field['properties']:
                    continue

                interpreter_schema[field['id']] = {
                    'id': field['id'], 'hrn': field['title'], 'weights': self.question_weights[question_id],
                    'option_ids': [option['id'] for option in field['properties']['choices']],
                    'option_vals': [option['label'] for option in field['properties']['choices']]
                }
                question_id += 1

        if target_file:
            with open(target_file, 'w') as j_target:
                j_target.write(json.dumps(interpreter_schema, indent=4))

        return interpreter_schema


if __name__ == "__main__":
    generator = FormSchemaGenerator(typeform_pat='[TYPEFORM PAT here...]',
                                    form_id='K4jATn6A', question_weights=QUESTION_WEIGHTS)
    print(json.dumps(generator.generate_score_scale(target_file='./score_scale.json'), indent=2))
    print(json.dumps(generator.generate_schema(target_file='./interpreter_schema.json'), indent=2))
