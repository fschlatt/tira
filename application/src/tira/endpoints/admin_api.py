import logging

from django.conf import settings
import traceback

from tira.authentication import auth
from tira.checks import check_permissions, check_resources_exist, check_conditional_permissions
from tira.forms import *
from django.http import HttpResponse, JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from http import HTTPStatus
import json
from datetime import datetime as dt
from tira.git_runner import check_that_git_integration_is_valid
from tira.ir_datasets_loader import run_irds_command

import tira.tira_model as model
import os
import tempfile
import zipfile

logger = logging.getLogger("tira")
logger.info("ajax_routes: Logger active")


def handle_get_model_exceptions(func):
    def decorate(request, *args, **kwargs):
        if request.method == 'GET':
            try:
                msg = func(*args, **kwargs)
                return JsonResponse({'status': 0, 'message': msg}, status=HTTPStatus.OK)
            except Exception as e:
                logger.exception(f"{func.__name__} failed with {e}", e)
                return JsonResponse({'status': 1, 'message': f"{func.__name__} failed with {e}"},
                                    status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return JsonResponse({'status': 1, 'message': f"{request.method} is not allowed."}, status=HTTPStatus.FORBIDDEN)

    return decorate


@check_permissions
@handle_get_model_exceptions
def admin_reload_data():
    model.build_model()
    if auth.get_auth_source() == 'legacy':
        auth.load_legacy_users()
    return "Model data was reloaded successfully"


@check_permissions
@handle_get_model_exceptions
def admin_reload_vms():
    model.reload_vms()
    return "VM data was reloaded successfully"


@check_permissions
@handle_get_model_exceptions
def admin_reload_datasets():
    model.reload_datasets()
    return "Dataset data was reloaded successfully"


@check_permissions
@handle_get_model_exceptions
def admin_reload_tasks():
    model.reload_tasks()
    return "Task data was reloaded successfully"


@check_conditional_permissions(restricted=True)
@handle_get_model_exceptions
def admin_reload_runs(vm_id):
    model.reload_runs(vm_id)
    return "Runs data was reloaded for {} on {} successfully"


@check_permissions
def admin_create_vm(request):  # TODO implement
    """ Hook for create_vm posts. Responds with json objects indicating the state of the create process. """

    if request.method == "POST":
        data = json.loads(request.body)

        return JsonResponse({'status': 0, 'message': f"Not implemented yet, received: {data}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for vm create"})


@check_permissions
def admin_archive_vm(request):
    return JsonResponse({'status': 1, 'message': f"Not implemented"}, status=HTTPStatus.NOT_IMPLEMENTED)


@check_permissions
def admin_modify_vm(request):
    if request.method == "POST":
        data = json.loads(request.body)

        return JsonResponse({'status': 0, 'message': f"Not implemented yet, received: {data}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for modify vm"})


@check_permissions
def admin_create_task(request, organizer_id):
    """ Create an entry in the model for the task. Use data supplied by a model.
     Return a json status message. """

    if request.method == "POST":
        data = json.loads(request.body)

        task_id = data["task_id"]
        featured = data["featured"]
        master_vm_id = data.get("master_vm_id", 'princess-knight') # dummy default VM
        master_vm_id = master_vm_id if master_vm_id else 'princess-knight' # default dummy vm
        require_registration = data['require_registration']
        require_groups = data['require_groups']
        restrict_groups = data['restrict_groups']

        if not model.organizer_exists(organizer_id):
            return JsonResponse({'status': 1, 'message': f"Organizer with ID {organizer_id} does not exist"})
        if model.task_exists(task_id):
            return JsonResponse({'status': 1, 'message': f"Task with ID {task_id} already exist"})
        if not model.vm_exists(master_vm_id):
            return JsonResponse({'status': 1, 'message': f"VM with ID {master_vm_id} does not exist"})

        new_task = model.create_task(task_id, data["name"], data["description"], featured, master_vm_id,
                                     organizer_id, data["website"],
                                     require_registration, require_groups, restrict_groups,
                                     help_command=data["help_command"], help_text=data["help_text"], allowed_task_teams=data["task_teams"])

        new_task = json.dumps(new_task, cls=DjangoJSONEncoder)
        return JsonResponse({'status': 0, 'context': new_task,
                             'message': f"Created Task with Id: {data['task_id']}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for admin_create_task"},
                        status=HTTPStatus.NOT_IMPLEMENTED)


@check_permissions
@check_resources_exist('json')
def admin_edit_task(request, task_id):
    """ Edit a task. Expects a POST message with all task data. """
    if request.method == "POST":
        data = json.loads(request.body)
        organizer = data["organizer"]
        featured = data["featured"]
        master_vm_id = data.get("master_vm_id", 'princess-knight') # default dummy vm
        master_vm_id = master_vm_id if master_vm_id else 'princess-knight' # default dummy vm
        require_registration = data['require_registration']
        require_groups = data['require_groups']
        restrict_groups = data['restrict_groups']

        if not model.organizer_exists(organizer):
            return JsonResponse({'status': 1, 'message': f"Organizer with ID {organizer} does not exist"})
        if not model.vm_exists(master_vm_id):
            return JsonResponse({'status': 1, 'message': f"VM with ID {master_vm_id} does not exist"})

        task = model.edit_task(task_id, data["name"], data["description"], featured, master_vm_id,
                               organizer, data["website"], require_registration, require_groups, restrict_groups,
                               help_command=data["help_command"], help_text=data["help_text"],
                               allowed_task_teams=data["task_teams"],
                               is_ir_task = data.get('is_information_retrieval_task', False),
                               irds_re_ranking_image = data.get('irds_re_ranking_image', ''),
                               irds_re_ranking_command = data.get('irds_re_ranking_command', ''),
                               irds_re_ranking_resource = data.get('irds_re_ranking_resource', '')
                               )

        return JsonResponse({'status': 0, 'context': json.dumps(task, cls=DjangoJSONEncoder),
                             'message': f"Edited Task with Id: {task_id}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for edit task"})


@check_permissions
@check_resources_exist('json')
def admin_delete_task(request, task_id):
    model.delete_task(task_id)
    return JsonResponse({'status': 0, 'message': f"Deleted task {task_id}"})


@check_permissions
def admin_add_dataset(request, task_id):
    """ Create an entry in the model for the task. Use data supplied by a model.
     Return a json status message. """
    if request.method == "POST":
        data = json.loads(request.body)

        if not all(k in data.keys() for k in ['dataset_id', 'name', 'task']):
            return JsonResponse({'status': 1, 'message': f"Error: Task, dataset name, and dataset ID must be set."})

        dataset_id_prefix = data["dataset_id"]
        dataset_name = data["name"]
        task_id_from_data = data["task"]

        if task_id_from_data != task_id:
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(f"Access forbidden.")

        upload_name = data.get("upload_name", "predictions.jsonl")
        command = data.get("evaluator_command", "")
        working_directory = data.get("evaluator_working_directory", "")
        measures = data.get("evaluation_measures", "")

        is_git_runner = data.get("is_git_runner", False)
        git_runner_image = data.get("git_runner_image", "")
        git_runner_command = data.get("git_runner_command", "")
        git_repository_id = data.get("git_repository_id", "")

        if not data.get("use_existing_repository", True):
            git_repository_id = model.get_git_integration(task_id=task_id).create_task_repository(task_id)

        master_vm_id = model.get_task(task_id)["master_vm_id"]

        if not model.task_exists(task_id):
            return JsonResponse({'status': 1, "message": f"Task with ID {task_id} does not exist"})
        if data['type'] not in {'test', 'training'}:
            return JsonResponse({'status': 1, "message": f"Dataset type must be 'test' or 'training'"})

        try:
            if data['type'] == 'training':
                ds, paths = model.add_dataset(task_id, dataset_id_prefix, "training", dataset_name, upload_name)
            elif data['type'] == 'test':
                ds, paths = model.add_dataset(task_id, dataset_id_prefix, "test", dataset_name, upload_name)

            model.add_evaluator(master_vm_id, task_id, ds['dataset_id'], command, working_directory, not measures,
                                is_git_runner, git_runner_image, git_runner_command, git_repository_id)
            path_string = '\n '.join(paths)
            return JsonResponse(
                {'status': 0, 'context': ds, 'message': f"Created new dataset with id {ds['dataset_id']}. "
                                                        f"Store your datasets in the following Paths:\n"
                                                        f"{path_string}"})
        except FileExistsError as e:
            logger.exception(e)
            return JsonResponse({'status': 1, 'message': f"A Dataset with this id already exists."})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for add dataset"})


@check_permissions
@check_resources_exist('json')
def admin_edit_dataset(request, dataset_id):
    """ Edit a dataset with the given dataset_id
    Send the new data of the dataset via POST. All these keys must be given and will be set:

    - name: New display name of the dataset
    - task: The associated task
    - master_id: ID of the vm that runs the evaluator for this dataset
    - type: 'training' or 'test'
    - evaluator_working_directory: working directory of the evaluator on the master vm
    - evaluator_command: command to be run on the master vm to evaluate the output of runs on the dataset
    - evaluation_measures: (str) the measures output by the evaluator. Sent as a string with:
        `
        Display Name of Measure1,key_of_measure_1\n
        Display Name of Measure2,key_of_measure_2\n
        ...
        `
    - is_git_runner
    - git_runner_image
    - git_runner_command
    - git_repository_id
    """
    if request.method == "POST":
        data = json.loads(request.body)

        dataset_name = data["name"]
        task_id = data["task"]
        is_confidential = not data['publish']

        command = data["evaluator_command"]
        working_directory = data["evaluator_working_directory"]
        measures = "" # here for legacy reasons. TIRA uses the measures provided by the evaluator

        is_git_runner = data["is_git_runner"]
        git_runner_image = data["git_runner_image"]
        git_runner_command = data["git_runner_command"]
        git_repository_id = data["git_repository_id"]

        print(data["use_existing_repository"])
        print(data["git_repository_id"])
        if not data["use_existing_repository"]:
            git_repository_id = model.get_git_integration(task_id=task_id).create_task_repository(task_id)

        upload_name = data["upload_name"]

        if not model.task_exists(task_id):
            return JsonResponse({'status': 1, "message": f"Task with ID {task_id} does not exist"})

        ds = model.edit_dataset(task_id, dataset_id, dataset_name, command, working_directory,
                                measures, upload_name, is_confidential, is_git_runner, git_runner_image,
                                git_runner_command, git_repository_id)

        from django.core.cache import cache
        model.git_pipeline_is_enabled_for_task(task_id, cache, force_cache_refresh=True)

        return JsonResponse(
            {'status': 0, 'context': ds, 'message': f"Updated Dataset {ds['dataset_id']}."})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for add dataset"})


def call_django_command_failsave(cmd, args):
    from django.core.management import call_command
    from io import StringIO
    import sys
    
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    
    error = None
    
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr
    
    try:
        call_command(cmd, **args)
    except Exception as e:
        error = str(e)
        error += '\n\n' + traceback.format_exc()
    
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    
    return {
        'stdout': str(captured_stdout.getvalue()),
        'stderr': str(captured_stderr.getvalue()),
        'error': error
    }


@check_permissions
def admin_import_ir_dataset(request):
    """ Create multiple datasets for the pased ir-dataset.
     Return a json status message. """
    if request.method == "POST":
        data = json.loads(request.body)

        if not all(k in data.keys() for k in ['dataset_id', 'name', 'task', 'image']):
            return JsonResponse({'status': 1, 'message': f"Error: dataset_id, name, task, and image must be set."})

        dataset_id_prefix = data["dataset_id"]
        dataset_name = data["name"]
        task_id = data["task"]

        upload_name = data.get("upload_name", "run.txt")
        evaluator_command = data.get("evaluator_command", "")
        working_directory = data.get("evaluator_working_directory", "")
        measures = data.get("evaluation_measures", "")

        is_git_runner = data.get("is_git_runner", True)
        git_runner_image = data.get("git_runner_image", data.get('image'))
        git_runner_command = data.get("git_runner_command", settings.IR_MEASURES_COMMAND)
        git_repository_id = model.get_git_integration(task_id=task_id).create_task_repository(task_id)
        irds_import_command = f'/irds_cli.sh --skip_qrels true --ir_datasets_id {data["dataset_id"]} --output_dataset_path $outputDir'
        irds_import_truth_command = f'/irds_cli.sh --skip_documents true --ir_datasets_id {data["dataset_id"]} --output_dataset_truth_path $outputDir'

        master_vm_id = None

        try:
            if data['type'] == 'training':
                ds, (dataset_path, dataset_truth_path) = model.add_dataset(task_id, dataset_id_prefix, "training", dataset_name, upload_name, irds_docker_image=git_runner_image, irds_import_command=irds_import_command, irds_import_truth_command=irds_import_truth_command)
            elif data['type'] == 'test':
                ds, (dataset_path, dataset_truth_path) = model.add_dataset(task_id, dataset_id_prefix, "test", dataset_name, upload_name, irds_docker_image=git_runner_image, irds_import_command=irds_import_command, irds_import_truth_command=irds_import_truth_command)
            else:
                return JsonResponse({'status': 1, 'message': f"Invalid data type. Expected training or test, got : "  + data['type']})
        except FileExistsError as e:
            logger.exception(e)
            return JsonResponse({'status': 1, 'message': f"A Dataset with this id already exists. Error: "  + str(e)})

        model.add_evaluator(master_vm_id, task_id, ds['dataset_id'], evaluator_command, working_directory, not measures,
                            is_git_runner, git_runner_image, git_runner_command, git_repository_id)

        try:
            ret = f'Output ({ds["irds_import_command"]}): \n'
            ret += run_irds_command(ds['task'], ds['dataset_id'], ds['irds_docker_image'], ds['irds_import_command'], dataset_path)

            ret += f'\n\n\nOutput ({ds["irds_import_truth_command"]}): \n'
            ret += run_irds_command(ds['task'], ds['dataset_id'], ds['irds_docker_image'], ds['irds_import_truth_command'], dataset_truth_path)
        except Exception as e:
            return JsonResponse({'status': 1, 'context': {}, 'message': f'Import of dataset failed with: {e}.'})

        return JsonResponse({'status': 0, 'context': {}, 'message': 'Imported dataset successfull.'})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for add dataset"})



@check_permissions
@check_resources_exist('json')
def admin_delete_dataset(request, dataset_id):
    model.delete_dataset(dataset_id)
    return JsonResponse({'status': 0, 'message': f"Deleted dataset {dataset_id}"})


@check_permissions
def admin_add_organizer(request, organizer_id):
    if request.method == "POST":
        data = json.loads(request.body)
        add_default_git_integrations = False

        if data['gitUrlToNamespace']:
            git_integration_is_valid, error_message = check_that_git_integration_is_valid(data['gitUrlToNamespace'], data['gitPrivateToken'])
            
            if not git_integration_is_valid:
                return JsonResponse({'status': 1, 'message': error_message})
        else:
            add_default_git_integrations = True

        model.edit_organizer(organizer_id, data["name"], data["years"], data["web"], data['gitUrlToNamespace'],
                             data['gitPrivateToken'])

        if add_default_git_integrations:
            git_integrations = [model.model.get_git_integration(settings.DEFAULT_GIT_INTEGRATION_URL, '<OMMITTED>')]
            model.model.edit_organizer(organizer_id, data["name"], data["years"], data["web"], git_integrations=git_integrations)

        auth.create_organizer_group(organizer_id, auth.get_user_id(request))
        return JsonResponse({'status': 0, 'message': f"Added Organizer {organizer_id}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for add organizer"})


@check_permissions
@check_resources_exist('json')
def admin_edit_organizer(request, organizer_id):
    if request.method == "POST":
        data = json.loads(request.body)
        
        if data['gitUrlToNamespace']:
            git_integration_is_valid, error_message = check_that_git_integration_is_valid(data['gitUrlToNamespace'], data['gitPrivateToken'])
            
            if not git_integration_is_valid:
                return JsonResponse({'status': 1, 'message': error_message})
        
        model.edit_organizer(organizer_id, data["name"], data["years"], data["web"], data['gitUrlToNamespace'], data['gitPrivateToken'])
        return JsonResponse({'status': 0, 'message': f"Updated Organizer {organizer_id}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for edit organizer"})


@check_conditional_permissions(restricted=True)
@check_resources_exist('json')
def admin_create_group(request, vm_id):
    """ this is a rest endpoint to grant a user permissions on a vm"""
    vm = model.get_vm(vm_id)
    message = auth.create_group(vm)
    return JsonResponse({'status': 0, 'message': message})


@check_conditional_permissions(restricted=True)
@check_resources_exist('json')
def admin_edit_review(request, dataset_id, vm_id, run_id):
    if request.method == "POST":
        data = json.loads(request.body)
        no_errors = data["no_errors"]
        output_error = data["output_error"]
        software_error = data.get("software_error", False) # Sometimes the frontend does not send the software error field
        comment = data["comment"]

        # sanity checks
        if no_errors and (output_error or software_error):
            JsonResponse({'status': 1, 'message': f"Error type is not clearly selected."})

        username = auth.get_user_id(request)
        has_errors = output_error or software_error
        has_no_errors = (not has_errors)

        s = model.update_review(dataset_id, vm_id, run_id, username, str(dt.utcnow()),
                                has_errors, has_no_errors, no_errors=no_errors,
                                invalid_output=output_error,
                                has_error_output=output_error, other_errors=software_error, comment=comment
                                )
        return JsonResponse({'status': 0, 'message': f"Updated review for run {run_id}"})

    return JsonResponse({'status': 1, 'message': f"GET is not implemented for edit organizer"})


@check_permissions
def admin_upload_dataset(request, task_id, dataset_id, dataset_type):
    if request.method != 'POST':
        return JsonResponse({"status": 1, "message": "GET is not allowed here."})

    if not dataset_id or dataset_id is None or dataset_id == 'None':
        return JsonResponse({"status": 1, "message": "Please specify the associated dataset."})

    if not dataset_type in ['input', 'truth']:
        return JsonResponse({"status": 1, "message": f"Invalid dataset_type. Expected 'input' or 'truth', but got: '{dataset_type}'"})

    dataset_suffix = '' if dataset_type == 'input' else '-truth'

    uploaded_file = request.FILES['file']

    if not uploaded_file.name.endswith(".zip"):
        return JsonResponse({"status": 1, "message": f"Invalid Upload. I expect a zip file, but got '{uploaded_file.name}'."})

    dataset = model.get_dataset(dataset_id)

    if not 'dataset_id' in dataset or dataset_id != dataset['dataset_id']:
        return JsonResponse({"status": 1, "message": f"Unknown dataset_id."})

    if dataset_id.endswith('-test'):
        dataset_prefix = 'test-'
    elif dataset_id.endswith('-training'):
        dataset_prefix = 'training-'
    else:
        return JsonResponse({"status": 1, "message": f"Unknown dataset_id."})

    target_directory = model.model.data_path / (dataset_prefix + 'datasets' + dataset_suffix) / task_id / dataset_id

    if not os.path.exists(target_directory):
        return JsonResponse({"status": 1, "message": f"Dataset directory 'target_directory' does not exist."})

    if len(os.listdir(target_directory)) > 0:
        return JsonResponse({"status": 1, "message": f"There is already some dataset uploaded. We prevent to overwrite data. Please create a new dataset (i.e., a new version) if you want to update the dataset. Please reach out to us if creating a new dataset would not solve your problem."})

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(tmp_dir + '/tmp.zip', 'wb+') as fp_destination:
            for chunk in uploaded_file.chunks():
                fp_destination.write(chunk)

        with zipfile.ZipFile(tmp_dir + '/tmp.zip', 'r') as zip_ref:
            zip_ref.extractall(target_directory)

        return JsonResponse({"status": 0, "message": f"Uploaded files '{os.listdir(target_directory)}' to '{target_directory}'."})
