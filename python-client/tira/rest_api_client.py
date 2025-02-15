import requests
import json
import pandas as pd
import os
import zipfile
import io
import docker
import time
from random import random
from tira.pyterrier_integration import PyTerrierIntegration
from tira.local_execution_integration import LocalExecutionIntegration


class Client():
    def __init__(self, api_key=None, failsave_retries=5, failsave_max_delay=15):
        self.tira_cache_dir = os.environ.get('TIRA_CACHE_DIR', os.path.expanduser('~') + '/.tira')
        self.json_cache = {}

        if api_key is None:
            self.api_key = self.load_settings()['api_key']
        else:
            self.api_key = api_key
        
        self.fail_if_api_key_is_invalid()
        self.pt = PyTerrierIntegration(self)
        self.local_execution = LocalExecutionIntegration(self)

        self.failsave_retries = failsave_retries
        self.failsave_max_delay = failsave_max_delay

    def load_settings(self):
        return json.load(open(self.tira_cache_dir + '/.tira-settings.json', 'r'))

    def fail_if_api_key_is_invalid(self):
        role = self.json_response('/api/role')
        
        if not role or 'status' not in role or 'role' not in role or 0 != role['status']:
            raise ValueError('It seems like the api key is invalid. Got: ', role)

    def datasets(self, task):
        return json.loads(self.json_response(f'/api/datasets_by_task/{task}')['context']['datasets'])

    def docker_software_id(self, approach):
        return self.docker_software(approach)['docker_software_id']

    def docker_software(self, approach):
        task, team, software = approach.split('/')
        docker_softwares = self.metadata_for_task(task, team)['context']['docker']['docker_softwares']

        for i in docker_softwares:
            if i['display_name'] == software:
                return i

    def metadata_for_task(self, task_name, team_name):
        return self.json_response(f'/api/task/{task_name}/user/{team_name}')

    def submissions(self, task, dataset):
        response = self.json_response(f'/api/submissions/{task}/{dataset}')['context']
        ret = []
        
        for vm in response['vms']:
            for run in vm['runs']:
                if 'review' in run:
                    for k,v in run['review'].items():
                        run['review_' + k] = v
                    del run['review']

                ret += [{**{'task': response['task_id'], 'dataset': response['dataset_id'], 'team': vm['vm_id']}, **run}]

        return pd.DataFrame(ret)

    def evaluations(self, task, dataset, join_submissions=True):
        response = self.json_response(f'/api/evaluations/{task}/{dataset}')['context']
        ret = []
        evaluation_keys = response['ev_keys']

        if join_submissions:
            runs_to_join = {}
            for _, i in self.submissions(task, dataset).iterrows():
                i = i.to_dict()
                runs_to_join[(i['team'], i['run_id'])] = {'software': i['software'], 'input_run_id': i['input_run_id'], 'is_upload': i['is_upload'], 'is_docker': i['is_docker']}

        for evaluation in response['evaluations']:
            run = {'task': response['task_id'], 'dataset': response['dataset_id'], 'team': evaluation['vm_id'], 'run_id': evaluation['input_run_id']}

            if join_submissions and (run['team'], run['run_id']) in runs_to_join:
                software = runs_to_join[(run['team'], run['run_id'])]
                for k,v in software.items():
                    run[k] = v

            for measure_id, measure in zip(range(len(evaluation_keys)), evaluation_keys):
                run[measure] = evaluation['measures'][measure_id]

            ret += [run]

        return pd.DataFrame(ret)

    def run_was_already_executed_on_dataset(self, approach, dataset):
        return self.get_run_execution_or_none(approach, dataset) is not None

    def get_run_execution_or_none(self, approach, dataset, previous_stage_run_id=None):
        task, team, software = approach.split('/')
        
        df_eval = self.evaluations(task=task, dataset=dataset)

        ret = df_eval[(df_eval['dataset'] == dataset) & (df_eval['software'] == software)]
        if len(ret) <= 0:
            return None
        
        if team:
            ret = ret[ret['team'] == team]

        if len(ret) <= 0:
            return None

        if previous_stage_run_id:
            ret = ret[ret['input_run_id'] == previous_stage_run_id]

        if len(ret) <= 0:
            return None

        return ret[['task', 'dataset', 'team', 'run_id']].iloc[0].to_dict()
        
    def download_run(self, task, dataset, software, team=None, previous_stage=None, return_metadata=False):
        ret = self.get_run_execution_or_none(f'{task}/{team}/{software}', dataset, previous_stage)
        if not ret:
            raise ValueError(f'I could not find a run for the filter criteria task="{task}", dataset="{dataset}", software="{software}", team={team}, previous_stage={previous_stage}')
        run_id = ret['run_id']
        
        ret = self.download_zip_to_cache_directory(**ret)
        ret = pd.read_csv(ret + '/run.txt', sep='\\s+', names=["query", "q0", "docid", "rank", "score", "system"])
        if return_metadata:
            return ret, run_id
        else:
            return ret

    def download_zip_to_cache_directory(self, task, dataset, team, run_id):
        target_dir = f'{self.tira_cache_dir}/extracted_runs/{task}/{dataset}/{team}'

        if os.path.isdir(target_dir + f'/{run_id}'):
            return target_dir + f'/{run_id}/output'

        self.download_and_extract_zip(f'https://www.tira.io/task/{task}/user/{team}/dataset/{dataset}/download/{run_id}.zip', target_dir)

        return target_dir + f'/{run_id}/output'
    
    def add_run_to_leaderboard(self, team, dataset, evaluation_run_id):
        ret = self.json_response(f'/publish/{team}/{dataset}/{evaluation_run_id}/true')
        
        if ('status' not in ret) or ('0' != ret['status']) or ('published' not in ret) or (not ret['published']):
            raise ValueError(f'Adding the run to the leaderboard failed. Got {ret}')

    def evaluate_run(self, team, dataset, run_id):
        ret = self.json_response(f'/grpc/{team}/run_eval/{dataset}/{run_id}')

        if status not in ret or '0' != str(ret['status']):
            raise ValueError(f'Failed to evaluate the run. Got {ret}')

        return ret

    def download_and_extract_zip(self, url, target_dir):
        for i in range(self.failsave_retries):
            try:
                r = requests.get(url, headers={"Api-Key": self.api_key})
                z = zipfile.ZipFile(io.BytesIO(r.content))
                z.extractall(target_dir)
                
                return
            except:
                sleep_time = 1+int(random()*self.failsave_max_delay)
                print(f'Error occured while fetching {url}. I will sleep {sleep_time} seconds and continue.')
                time.sleep(sleep_time)

    def get_authentication_cookie(self, user, password):
        import requests

        resp = requests.get('https://www.tira.io/session/csrf', headers={'x-requested-with': 'XMLHttpRequest'})

        header = {
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'cookie': '_forum_session=' + resp.cookies['_forum_session'],
            'x-csrf-token': resp.json()['csrf'],
            'x-requested-with': 'XMLHttpRequest'
        }

        resp = requests.post('https://www.tira.io/session', data=f'login={user}&password={password}', headers=header)

        return f'_t={resp.cookies["_t"]}; _forum_session={resp.cookies["_forum_session"]}'

    def run_software(self, approach, dataset, resources, rerank_dataset='none'):
        task, team, software = approach.split('/')
        authentication_cookie = self.get_authentication_cookie(self.load_settings()['user'], self.load_settings()['password'])
        
        software_id = self.docker_software_id(approach)
        if not software_id:
            raise ValueError(f'Could not find software id for "{approach}". Got: "{software_id}".')
        
        url = f'https://www.tira.io/grpc/{task}/{team}/run_execute/docker/{dataset}/{software_id}/{resources}/{rerank_dataset}'
        print(f'Start software...\n\t{url}\n')

        csrf_token = self.get_csrf_token()
        headers = {   
            #'Api-Key': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cookie': authentication_cookie,
            'x-csrftoken': csrf_token,
        }

        ret = requests.post(url, headers=headers, json={"csrfmiddlewaretoken": csrf_token, "action": "post"})
        ret = ret.content.decode('utf8')
        print(ret)
        ret = json.loads(ret)
        assert ret['status'] == 0

    def get_csrf_token(self):
        ret = requests.get('https://www.tira.io/', headers={"Api-Key": self.api_key})

        return ret.content.decode('utf-8').split('name="csrfmiddlewaretoken" value="')[1].split('"')[0]

    def json_response(self, endpoint, params=None):
        cache_key = endpoint + '----' + ('' if not params else json.dumps(params))
        
        if cache_key in self.json_cache:
            return self.json_cache[cache_key]
        
        headers = {"Api-Key": self.api_key, "Accept": "application/json"}
        resp = requests.get(url='https://www.tira.io' + endpoint, headers=headers, params=params)
        
        if resp.status_code not in {200, 202}:
            raise ValueError('Got statuscode ', resp.status_code, 'for ', endpoint, '. Got', resp)
        
        self.json_cache[cache_key] = resp.json()

        return self.json_cache[cache_key]

