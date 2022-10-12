import tempfile
import os
import json
from pathlib import Path
from glob import glob
import docker
import pandas as pd
from packaging import version


def ___load_softwares():
    softwares = [json.loads(i) for i in open('.tira/submitted-software.jsonl')]
    
    return {i['TIRA_TASK_ID'] + '/' + i['TIRA_VM_ID'] + '/' + i['TIRA_SOFTWARE_NAME']: i for i in softwares}


def __num(s):
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def __load_evaluators():
    evaluators = [json.loads(i) for i in open('.tira/evaluators.jsonl')]
    ret = {i['TIRA_DATASET_ID']: i for i in evaluators}
    
    for evaluator in evaluators:
        dataset_id = evaluator['TIRA_DATASET_ID']
        current_version = version.parse(ret[dataset_id]['TIRA_EVALUATION_IMAGE_TO_EXECUTE'].split(':')[-1])
        available_version = version.parse(evaluator['TIRA_EVALUATION_IMAGE_TO_EXECUTE'].split(':')[-1])
        
        if available_version > current_version:
            ret[dataset_id] = evaluator
    
    return ret


def __load_job_data(job_file):
    job = [i.split('=') for i in open(job_file, 'r')]
    return {k.strip():v.strip() for k,v in job}


def all_evaluated_appraoches():
    id_to_software_name = {int(i['TIRA_SOFTWARE_ID'].split('docker-software-')[1]):i['TIRA_SOFTWARE_NAME'] for i in ___load_softwares().values()}
    ret = []
    for evaluation in glob('*/*/*/evaluation'):
        job_dir = glob(evaluation + '/../job-executed-on*.txt')
        if len(job_dir) != 1:
            raise ValueError('Can not handle multiple job definitions: ', job_dir)
            
        job_definition = __load_job_data(job_dir[0])
        job_identifier = job_definition['TIRA_TASK_ID'] + '/' + job_definition['TIRA_VM_ID'] + '/' + id_to_software_name[int(job_definition['TIRA_SOFTWARE_ID'].split('docker-software-')[1])]
        
        for eval_run in glob(f"{evaluation}/*/output/"):
            
            try:
                i = {'approach': job_identifier, 'dataset': job_definition['TIRA_DATASET_ID']}
                i.update(__load_output(eval_run, evaluation=True))
                ret += [i]
            except:
                pass

    return pd.DataFrame(ret)


def __extract_image_and_command(identifier, evaluator=False):
    softwares = ___load_softwares() if not evaluator else __load_evaluators()
    
    if identifier in softwares and not evaluator:
        return softwares[identifier]['TIRA_IMAGE_TO_EXECUTE'], softwares[identifier]['TIRA_COMMAND_TO_EXECUTE']
    if evaluator:
        for k, v in softwares.items():
            if k.startswith(identifier):
                return v['TIRA_DATASET_ID'], v['TIRA_EVALUATION_IMAGE_TO_EXECUTE'], v['TIRA_EVALUATION_COMMAND_TO_EXECUTE']
    
    raise ValueError(f'There is no {("evaluator" if evaluator else "software")} identified by "{identifier}". Choices are: {sorted(list(softwares))}')


def __load_output(directory, evaluation=False, verbose=False):
    files = glob(str(directory) + '/*' )
    
    if evaluation:
        files = [i for i in files if i.endswith('.prototext')]
    
    if len(files) != 1:
        raise ValueError('Expected exactly one output file. Got: ', files)
    
    files = files[0]
    
    if verbose:
        print(f'Read file from {files}')
    
    if evaluation:
        ret = {}
        for i in [i for i in open(files, 'r').read().split('measure') if 'key:' in i and 'value:' in i]:
            key = i.split('key:')[1].split('value')[0].split('"')[1]
            value = i.split('key:')[1].split('value')[1].split('"')[1]
            
            ret[key.strip()] = __num(value.strip())
            
        return ret
    else:
        return pd.read_json(files, lines=True, orient='records')


def __normalize_command(cmd):
    to_normalize = {'inputRun': '/tira-data/output',
                    'outputDir': '/tira-data/output',
                    'inputDataset': '/tira-data/input'
                   }
    
    if 'inputRun' in cmd:
        to_normalize['outputDir'] = '/tira-data/eval_output'
    
    for k,v in to_normalize.items():
        cmd = cmd.replace('$' + k, v).replace('${' + k + '}', v)
    
    return cmd


def run(identifier=None, image=None, command=None, data=None, evaluate=False, verbose=False):
    if image is None or command is None:
        image, command = __extract_image_and_command(identifier)
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    
    tmp_dir = Path(tempfile.TemporaryDirectory().name)
    input_dir = tmp_dir / 'input'
    output_dir = tmp_dir / 'output'
    eval_output_dir = tmp_dir / 'eval_output'

    os.makedirs(str(input_dir.absolute()), exist_ok=True)
    os.makedirs(str(output_dir.absolute()), exist_ok=True)
    os.makedirs(str(eval_output_dir.absolute()), exist_ok=True)

    if verbose:
        print(f'Write {len(data)} records to {input_dir}/input.jsonl')
    
    data.to_json(input_dir / 'input.jsonl', lines=True, orient='records')
    command = __normalize_command(command)
    
    if verbose:
        print(f'Run software with: docker run --rm -ti -v {tmp_dir}:/tira-data --entrypoint sh {image} {command}')
    
    client.containers.run(image, entrypoint='sh', command=f'-c "{command}"', volumes={str(tmp_dir): {'bind': '/tira-data/', 'mode': 'rw'}})
    
    if evaluate:
        evaluate, image, command = __extract_image_and_command(evaluate, evaluator=True)
        command = __normalize_command(command)
        if verbose:
            print(f'Evaluate software with: docker run --rm -ti -v {tmp_dir}:/tira-data --entrypoint sh {image} {command}')
        
        client.containers.run(image, entrypoint='sh', command=f'-c "{command}"', volumes={str(tmp_dir): {'bind': '/tira-data/', 'mode': 'rw'}})

    if evaluate:
        approach_name = identifier if identifier else f'"{command}"@{image}'
        eval_results = {'approach': approach_name, 'evaluate': evaluate}
        eval_results.update(__load_output(eval_output_dir, evaluation=True, verbose=verbose))
        return __load_output(output_dir, verbose=verbose), pd.DataFrame([eval_results])
    else:
        return __load_output(output_dir, verbose=verbose)

