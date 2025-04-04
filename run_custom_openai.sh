# Script to run LLANA on all Bayesmark tasks.

#!/bin/bash
trap "kill -- -$BASHPID" EXIT

# This is the OpenAI LLM Engine
provider="openai"
ENGINE="gpt-3.5-turbo"




# for dataset in "digits"
# do
for model in "Custom_Scoring"
do
    python3 exp_custom/run_custom.py --model $model --num_seeds 1 --sm_mode discriminative --engine $ENGINE --provider $provider
    # sleep 10
done
# done
