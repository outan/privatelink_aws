#!/usr/bin/env python3
import os

import aws_cdk as cdk

from privatelink_aws.provider_vpc_stack import ProviderVpcStack
from privatelink_aws.consumer_vpc_stack import ConsumerVpcStack

app = cdk.App()

provider_vpc_stack = ProviderVpcStack(app, "ProviderVpcStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)

consumer_vpc_stack = ConsumerVpcStack(app, "ConsumerVpcStack",
    provider_endpoint_service=provider_vpc_stack.endpoint_service,
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)

app.synth()
