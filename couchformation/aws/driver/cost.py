##
##

import logging
import botocore.exceptions
from couchformation.aws.driver.base import CloudBase, AWSDriverError

logger = logging.getLogger('couchformation.aws.driver.cost')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


class Cost(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_cost(self, machine_type: str, region: str):
        filters = [
            {
                'Type': 'TERM_MATCH',
                'Field': 'instanceType',
                'Value': machine_type
            }
        ]
        try:
            result = self.cost_client.get_attribute_values(ServiceCode='AmazonEC2', AttributeName='instanceType')
            print(result)
            result = self.cost_client.get_products(ServiceCode='AmazonEC2', Filters=filters)
            print(result)
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('AccessDeniedException'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting cost for machine type: {err}")
