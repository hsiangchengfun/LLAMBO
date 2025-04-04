import os
import pickle
import json
import argparse
import logging
import warnings
import random
import pandas as pd
import numpy as np
from llambo.llambo import LLAMBO
from bayesmark.bbox_utils import get_bayesmark_func
from sklearn.metrics import get_scorer
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)


def setup_logging(log_name):
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_name, mode='w')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

CUSTOM_TASK_MAP = {
    #TODO
    'digits': ['classification', 'accuracy'],
    'CMRR_score': ['regression', 'neg_mean_squared_error'],
    'Offset_score': ['regression', 'neg_mean_squared_error'],
}

PRIVATE_TASK_MAP = {
}


class CustomExpRunner:
    def __init__(self, task_context, seed):
        self.seed = seed
        self.model = task_context['model']
        self.task = task_context['task']
        self.metric = task_context['metric']
        # self.dataset = dataset
        self.hyperparameter_constraints = task_context['hyperparameter_constraints']
        self.bbox_func = None#get_bayesmark_func(self.model, self.task, dataset['test_y'])
    
    def generate_initialization(self, n_samples):
        '''
        Generate initialization points for BO search
        Args: n_samples (int)
        Returns: list of dictionaries, each dictionary is a point to be evaluated
        '''

        # Read from fixed initialization points (all baselines see same init points)
        # init_configs = pd.read_json(f'bayesmark/configs/SVM/{self.seed}.json').head(n_samples)
        # print(self.model)
        # print(f'custom_config/configs/{self.model}/{self.seed}.json')
        init_configs = pd.read_json(f'custom_config/configs/{self.model}/{self.seed}.json').head(n_samples)
        init_configs = init_configs.to_dict(orient='records')

        assert len(init_configs) == n_samples

        return init_configs

    def evaluate_point(self, candidate_config):
        '''
        Evaluate a single point on bbox
        Args: candidate_config (dict), dictionary containing point to be evaluated
        Returns: (dict, dict), first dictionary is candidate_config (the evaluated point), second dictionary is fvals (the evaluation results)
        fvals can contain an arbitrary number of items, but also must contain 'score' (which is what LLAMBO optimizer tries to optimize)
        fvals = {
            'score': float,                     -> 'score' is what the LLAMBO optimizer tries to optimize
            'generalization_score': float
        }
        '''


        for hyperparam, value in candidate_config.items():
            if self.hyperparameter_constraints[hyperparam][0] == 'int':
                candidate_config[hyperparam] = int(value)

        # TODO feed candidate_config to simulator
        # TODO take feedback of simulator to out-scorer to get a score, here is a dummy
        cv_score = candidate_config["NoC_Width"]*0.3 + candidate_config["L1CacheSize"]*0.7
        
        
        if self.metric == 'neg_mean_squared_error':
            cv_score = -cv_score

        return candidate_config, {'score': cv_score}



if __name__ == '__main__':
    # parse input arguments
    parser = argparse.ArgumentParser()
    # parser.add_argument('--dataset', type=str)
    parser.add_argument('--model', type=str)
    parser.add_argument('--num_seeds', type=int)
    parser.add_argument('--engine', type=str) # temporary fix to run multiple in parallel
    parser.add_argument('--sm_mode', type=str)
    parser.add_argument('--provider', type=str, default='ollama')

    args = parser.parse_args()
    # dataset = args.dataset
    model = args.model
    num_seeds =args.num_seeds
    chat_engine = args.engine
    sm_mode = args.sm_mode
    provider = args.provider

    assert sm_mode in ['discriminative', 'generative']
    if sm_mode == 'generative':
        top_pct = 0.25
    else:
        top_pct = None

    # Load training and testing data
    # if dataset in CUSTOM_TASK_MAP:
    #     TASK_MAP = CUSTOM_TASK_MAP
    #     pickle_fpath = f'custom_dataset/{dataset}.pickle'
    #     with open(pickle_fpath, 'rb') as f:
    #         data = pickle.load(f)
    #     X_train = data['train_x']
    #     y_train = data['train_y']
    #     X_test = data['test_x']
    #     y_test = data['test_y']
    # elif dataset in PRIVATE_TASK_MAP:
    #     TASK_MAP = PRIVATE_TASK_MAP
    #     pickle_fpath = f'private_data/{dataset}.pickle'
    #     with open(pickle_fpath, 'rb') as f:
    #         data = pickle.load(f)
    #     X_train = data['train_x']
    #     y_train = data['train_y']
    #     X_test = data['test_x']
    #     y_test = data['test_y']
    # else:
    #     raise ValueError(f'Invalid dataset: {dataset}')


    # Describe task context
    task_context = {}
    task_context['model'] = model
    task_context['task'] = 'regression'#TASK_MAP[dataset][0]
    task_context['tot_feats'] = 0 #X_train.shape[1]
    task_context['cat_feats'] = 0       # bayesmark datasets only have numerical features
    task_context['num_feats'] = 0 #X_train.shape[1]
    task_context['n_classes'] = 0 #len(np.unique(y_train))
    task_context['metric'] = 'accuracy' #TASK_MAP[dataset][1]
    task_context['lower_is_better'] = True if 'neg' in task_context['metric'] else False
    task_context['num_samples'] = 0 #X_train.shape[0]
    with open('hp_configurations/custom.json', 'r') as f:
        task_context['hyperparameter_constraints'] = json.load(f)[model]
    
    print("="*20)
    print(task_context)
    print("="*20)
    
    # define result save directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    save_res_dir = f'{script_dir}/{provider}/{chat_engine}/results_{sm_mode}/{model}'
    if not os.path.exists(save_res_dir):
        os.makedirs(save_res_dir)
    # define logging directory
    logging_fpath = f'{script_dir}/{provider}/{chat_engine}/logs_{sm_mode}/{model}.log'
    if not os.path.exists(os.path.dirname(logging_fpath)):
        os.makedirs(os.path.dirname(logging_fpath))
    setup_logging(logging_fpath)

    tot_llm_cost = 0
    for seed in range(num_seeds):
        logger.info('='*80)
        logger.info(f'Executing LLAMBO ({sm_mode} | {provider} | {chat_engine} | top_pct: {top_pct}) to tune {model} with seed {seed+1} / {num_seeds}...')
        logger.info(f'Task context: {task_context}')
        print("x"*20)
        data=None

        benchmark = CustomExpRunner(task_context, seed)

        if provider == 'ollama':
            n_trials = 10
        else:
            n_trials = 20


        # instantiate LLAMBO
        llambo = LLAMBO(task_context, sm_mode, n_candidates=10, n_templates=2, n_gens=10,
                        alpha=0.1, n_initial_samples=5, n_trials=n_trials, init_f=benchmark.generate_initialization,
                        bbox_eval_f=benchmark.evaluate_point, chat_engine=chat_engine, top_pct=top_pct)
        llambo.seed = seed
        configs, fvals = llambo.optimize()


        logger.info(f'[LLAMBO] Query cost: {sum(llambo.llm_query_cost):.4f}')
        logger.info(f'[LLAMBO] Query time: {sum(llambo.llm_query_time):.4f}')
        tot_llm_cost += sum(llambo.llm_query_cost)

        # save search history
        search_history = pd.concat([configs, fvals], axis=1)
        search_history.to_csv(f'{save_res_dir}/{seed}.csv', index=False)

        logger.info(search_history)
        logger.info(f'[LLAMBO] RUN COMPLETE, saved results to {save_res_dir}...')

        # save search info
        search_info = {
            'llm_query_cost_breakdown': llambo.llm_query_cost,
            'llm_query_time_breakdown': llambo.llm_query_time,
            'llm_query_cost': sum(llambo.llm_query_cost),
            'llm_query_time': sum(llambo.llm_query_time),
        }
        with open(f'{save_res_dir}/{seed}_search_info.json', 'w') as f:
            json.dump(search_info, f)

    logger.info('='*80)
    logger.info(f'[LLAMBO] {seed+1} evaluation runs complete! Total cost: ${tot_llm_cost:.4f}')
