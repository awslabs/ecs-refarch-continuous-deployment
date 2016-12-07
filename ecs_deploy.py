"""
Licensed under the Apache License, Version 2.0 (the "License").
You may not use this file except in compliance with the License.
A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "LICENSE" file accompanying this file.  This file is distributed
on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
express or implied.  See the License for the specific language governing
permissions and limitations under the License.
"""

import boto3
import json
import logging
import zipfile
from botocore.client import Config

codepipeline = boto3.client('codepipeline')
ecs = boto3.client('ecs')


def handler(event, context):
    job = event['CodePipeline.job']
    credentials = job['data']['artifactCredentials']
    location = job['data']['inputArtifacts'][0]['location']['s3Location']
    user_parameters = json.loads(
        job['data']['actionConfiguration']['configuration']['UserParameters'])
    cluster = user_parameters['Cluster']
    service = user_parameters['Service']
    family = user_parameters['Family']

    try:
        task_definition = ecs.describe_task_definition(taskDefinition=family)
        new_image = _get_new_image(credentials, location)

        _deploy(task_definition['taskDefinition'], new_image, cluster, service)
        codepipeline.put_job_success_result(jobId=job['id'])
    except Exception as e:
        logging.exception(e)
        codepipeline.put_job_failure_result(
                jobId=job['id'],
                failureDetails={'type': 'JobFailed', 'message': str(e)})


def _get_new_image(credentials, location):
    s3 = boto3.client('s3',
                      aws_access_key_id=credentials['accessKeyId'],
                      aws_secret_access_key=credentials['secretAccessKey'],
                      aws_session_token=credentials['sessionToken'],
                      config=Config(signature_version='s3v4'))
    bucket_name = location['bucketName']
    object_key = location['objectKey']
    file_name = '/tmp/' + object_key.rsplit('/', 2)[-1]

    s3.download_file(bucket_name, object_key, file_name)

    with zipfile.ZipFile(file_name) as myzip:
        with myzip.open('build.out') as myfile:
            return myfile.read()


def _deploy(task_definition, new_image, cluster, service):
    family = task_definition['family']
    volumes = task_definition['volumes']
    container_definitions = task_definition['containerDefinitions']
    new_image_repo = new_image[0:new_image.rindex(':')]

    for container in task_definition['containerDefinitions']:
        if ':' in container['image']:
            colon_index = container['image'].rindex(':')
            container_repo = container['image'][0:colon_index]
            if container_repo == new_image_repo:
                container['image'] = new_image

    ecs.register_task_definition(family=family, volumes=volumes,
                                 containerDefinitions=container_definitions)
    ecs.update_service(cluster=cluster, service=service,
                       taskDefinition=family, desiredCount=1)
