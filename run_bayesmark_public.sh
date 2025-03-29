# Script to run LLAMBO on all Bayesmark tasks.

#!/bin/bash
trap "kill -- -$BASHPID" EXIT

# This is the OpenAI LLM Engine
#ENGINE="gpt-3.5-turbo"
#ENGINE="Llama3-TAIDE-LX-70B-Chat"
#ENGINE="Llama-3.1-405B-Instruct-FP8"
#ENGINE="Llama-3.3-70B-Instruct"
ENGINE="llama3.1:8b-instruct-q8_0"
#ENGINE="llama3.1:8b-instruct-fp16"

#for dataset in "digits" "wine" "diabetes" "iris" "breast"
for dataset in "digits"
do
    for model in "RandomForest" #"SVM" "DecisionTree" "MLP_SGD" "AdaBoost"
    do
        python3 exp_bayesmark/run_bayesmark.py --dataset $dataset --model $model --num_seeds 1 --sm_mode discriminative --engine $ENGINE
        sleep 60
    done
done
