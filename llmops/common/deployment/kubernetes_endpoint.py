"""
This module creates Kubernetes AML online endpoint as flow deployment process.

Args:
--base_path: Base path of the use case. Where flows, data,
and experiment.yaml are expected to be found.
--subscription_id: The Azure subscription ID. If this argument is not
specified, the SUBSCRIPTION_ID environment variable is expected to be provided.
--build_id: The unique identifier for build execution.
This argument is not required but will be added as a run tag if specified.
--env_name: The environment name for execution and deployment. This argument
is not required but will be used to read experiment overlay files if specified.
--output_file: The file path for the output file needed for
the endpoint principal. This argument is required to specify the path
to the output file necessary for the endpoint principal.
"""

import json
import argparse
from typing import Optional
from dotenv import load_dotenv

from azure.ai.ml import MLClient
from azure.ai.ml.entities import KubernetesOnlineEndpoint
from azure.identity import DefaultAzureCredential

from llmops.common.logger import llmops_logger
from llmops.common.experiment_cloud_config import ExperimentCloudConfig
from llmops.common.config_utils import ExperimentConfig

logger = llmops_logger("provision_endpoint")


def create_kubernetes_endpoint(
    env_name: str,
    base_path: Optional[str] = None,
    build_id: Optional[str] = None,
    subscription_id: Optional[str] = None,
    output_file: Optional[str] = None,
):
    config = ExperimentCloudConfig(subscription_id=subscription_id, env_name=env_name)
    experiment_config = ExperimentConfig(flow_name=base_path, environment=env_name)

    ml_client = MLClient(
        DefaultAzureCredential(),
        config.subscription_id,
        config.resource_group_name,
        config.workspace_name,
    )

    kubernetes_endpoints = experiment_config.deployment_configs['kubernetes_endpoint']

    for elem in kubernetes_endpoints:
        if "ENDPOINT_NAME" in elem and "ENV_NAME" in elem:
            if env_name == elem["ENV_NAME"]:
                endpoint_name = elem["ENDPOINT_NAME"]
                endpoint_desc = elem["ENDPOINT_DESC"]
                compute_name = elem["COMPUTE_NAME"]

                endpoint = KubernetesOnlineEndpoint(
                    name=endpoint_name,
                    description=endpoint_desc,
                    compute=compute_name,
                    auth_mode="key",
                    tags={"build_id": build_id} if build_id else {},
                )

                logger.info(f"Creating endpoint {endpoint.name}")
                ml_client.online_endpoints.begin_create_or_update(
                    endpoint=endpoint
                ).result()

                logger.info(f"Obtaining endpoint {endpoint.name} identity")
                principal_id = ml_client.online_endpoints.get(
                    endpoint_name
                ).identity.principal_id
                if output_file is not None:
                    with open(output_file, "w") as out_file:
                        out_file.write(str(principal_id))


def main():
    parser = argparse.ArgumentParser("provision_kubernetes_endpoints")
    parser.add_argument(
        "--subscription_id",
        type=str,
        help="Subscription ID, overrides the SUBSCRIPTION_ID environment variable",
        default=None,
    )
    parser.add_argument(
        "--base_path",
        type=str,
        help="Base path of the use case",
        required=True,
    )
    parser.add_argument(
        "--env_name",
        type=str,
        help="environment name(dev, test, prod) for execution and deployment, overrides the ENV_NAME environment variable",
        default=None,
    )
    parser.add_argument(
        "--build_id",
        type=str,
        help="Unique identifier for build execution",
        default=None,
    )
    parser.add_argument(
        "--output_file",
        type=str,
        help="Outfile file needed for endpoint principal.",
        required=None,
    )
    args = parser.parse_args()

    create_kubernetes_endpoint(
        args.env_name,
        args.base_path,
        args.build_id,
        args.subscription_id,
        args.output_file,
    )


if __name__ == "__main__":
    # Load variables from .env file into the environment
    load_dotenv(override=True)

    main()
