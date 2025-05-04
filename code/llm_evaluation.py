import math
import csv
from llama_cpp import *
from os.path import join
import time
from llm_chat import *
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
import nltk
from nltk.tokenize import word_tokenize
from nltk.util import ngrams
from nltk.translate.meteor_score import single_meteor_score


# nltk.download('punkt')
# nltk.download('punkt_tab')
# nltk.download('wordnet')

def calculate_perplexity(reply: str) -> float:
    print(f"[DEBUG] Calculating perplexity via llama_cpp for reply: {reply!r}")

    out = llm(
        reply,
        max_tokens=0,  
        echo=True,    
        logprobs=1,     
    )

    # grab the list of token log-probabilities
    logprobs_data = out["choices"][0]["logprobs"]

    lp = logprobs_data.get("token_logprobs") if logprobs_data else None

    if not lp:
        print("[ERROR] No logprobs returned or logprobs is empty, cannot compute perplexity.")
        return float("inf")

    # Skip None values and calculate PPL based only on valid log-probs
    valid_lp = [logp for logp in lp if logp is not None]

    if not valid_lp:
        print("[ERROR] No valid logprobs, cannot compute perplexity.")
        return float("inf")

    # PPL = exp(- average log-prob)
    try:
        ppl = math.exp(-sum(valid_lp) / len(valid_lp))
    except Exception as e:
        print(f"[ERROR] Error calculating perplexity: {e}")
        return float("inf")

    return ppl

def evaluate_perplexity(reply: str, player_input: str, npc_context: dict) -> float:
    print(f"[DEBUG] Evaluating perplexity for NPC reply: {reply!r}")
    print(f"[DEBUG] player said: {player_input!r}")
    ppl = calculate_perplexity(reply)
    print(f"[DEBUG] perplexity = {ppl:.4f}")
    return ppl

def calculate_bleu(reference: str, candidate: str) -> float:
    reference_tokens = [word_tokenize(reference.lower())]  # Tokenize the reference and make it lowercase
    candidate_tokens = word_tokenize(candidate.lower())   # Tokenize the candidate and make it lowercase
    
    smoothing_function = SmoothingFunction().method1  # You can choose other methods

    # Calculate BLEU score (using up to 4-grams)
    bleu_score = sentence_bleu(reference_tokens, candidate_tokens, 
                               weights=(1, 0, 0, 0),  # Unigram only
                               smoothing_function=smoothing_function)
    
    return bleu_score

def evaluate_bleu(reference: str, candidate: str) -> float:
    print(f"[DEBUG] Evaluating BLEU for reference: {reference!r}")
    print(f"[DEBUG] candidate: {candidate!r}")
    
    bleu_score = calculate_bleu(reference, candidate)
    
    print(f"[DEBUG] BLEU score: {bleu_score:.4f}")
    return bleu_score

def calculate_meteor(reference: str, candidate: str) -> float:
    print(f"[DEBUG] Calculating METEOR for reference: {reference!r} and candidate: {candidate!r}")
    
    # Tokenize both the reference and candidate sentences
    reference_tokens = word_tokenize(reference.lower())  # Tokenize and convert to lowercase
    candidate_tokens = word_tokenize(candidate.lower())   # Tokenize and convert to lowercase
    
    # Compute METEOR score using the tokenized sentences
    meteor_score_value = single_meteor_score(reference_tokens, candidate_tokens)
    return meteor_score_value

def evaluate_meteor(reference: str, candidate: str) -> float:
    print(f"[DEBUG] Evaluating METEOR score for reference: {reference!r} and candidate: {candidate!r}")
    meteor_score_value = calculate_meteor(reference, candidate)
    print(f"[DEBUG] METEOR score: {meteor_score_value:.4f}")
    return meteor_score_value

def calculate_distinct(response: str, n: int = 1) -> float:
    print(f"[DEBUG] Calculating Distinct-{n} for response: {response!r}")
    
    # Tokenize the response into words
    tokens = word_tokenize(response.lower())  # Tokenize and convert to lowercase
    
    # Create n-grams (unigrams, bigrams, etc.)
    n_grams = list(ngrams(tokens, n))  # Create n-grams (1 for unigram, 2 for bigram)
    
    # Calculate Distinct score: unique n-grams / total n-grams
    distinct_score = len(set(n_grams)) / len(n_grams) if len(n_grams) > 0 else 0.0
    return distinct_score

# Evaluate Distinct Score
def evaluate_distinct(response: str, n: int = 1) -> float:
    print(f"[DEBUG] Evaluating Distinct-{n} for response: {response!r}")
    distinct_score = calculate_distinct(response, n)
    print(f"[DEBUG] Distinct-{n} score: {distinct_score:.4f}")
    return distinct_score
    
# def batch_evaluate(full_prompt: str, player_prompts, num_tests=100):
#     all_scores = {
#         'sentiment': [],
#         'perplexity': [],
#         'bleu': [],
#         'meteor': [],
#         'distinct': []
#     }

#     # Run the prompt sequentially (one test after another)
#     for i in range(num_tests):
#         print(f"[DEBUG] Test {i+1}/{num_tests}: Sending prompt to NPC...")

#         # Iterate through player prompts
#         for player_prompt in player_prompts:
#             # Combine system prompt, player prompt, and global prompt
#             full_prompt_with_player = f"{GLOBAL_SYSTEM_PROMPT}\n{full_prompt}\n{player_prompt}"

#             # Get NPC response and analyze sentiment
#             reply, mood = get_npc_response(player_prompt=full_prompt_with_player, local_prompt="", history=None)

#             # Calculate the metrics for the response
#             sentiment_score = analyze_sentiment(reply)
#             perplexity_score = calculate_perplexity(reply)
#             bleu_score = calculate_bleu(full_prompt_with_player, reply)
#             meteor_score = calculate_meteor(full_prompt_with_player, reply)
#             distinct_score = calculate_distinct(reply)

#             print(f"[DEBUG] Sentiment Score: {sentiment_score['compound']}")
#             print(f"[DEBUG] Perplexity Score: {perplexity_score}")
#             print(f"[DEBUG] BLEU Score: {bleu_score}")
#             print(f"[DEBUG] METEOR Score: {meteor_score}")
#             print(f"[DEBUG] Distinct Score: {distinct_score}")
            
#             # Store the scores for each player prompt
#             all_scores['sentiment'].append(sentiment_score['compound'])
#             all_scores['perplexity'].append(perplexity_score)
#             all_scores['bleu'].append(bleu_score)
#             all_scores['meteor'].append(meteor_score)
#             all_scores['distinct'].append(distinct_score)

#     # Calculate averages for each score
#     average_scores = {
#         metric: sum(scores) / len(scores) for metric, scores in all_scores.items()
#     }

#     return average_scores

# def save_results_to_csv(results, filename="evaluation_results.csv"):
#     with open(filename, mode='w', newline='') as file:
#         writer = csv.writer(file)
#         # Add column headers to include average time
#         writer.writerow(["Test", "Sentiment", "Perplexity", "BLEU", "METEOR", "Distinct", "Avg Time (s)"])

#         for i, result in enumerate(results):
#             writer.writerow([i+1, *result])  # This will include the time in the results as well

# def run_evaluation(local_prompt_list, player_prompt_list, num_tests=50):
#     all_results = []

#     for local_prompt in local_prompt_list:
#         print(f"[INFO] Evaluating system prompt: {local_prompt}")

#         # For each test, we need to calculate scores for 5 different player prompts
#         for test_num in range(num_tests):
#             print(f"[INFO] Running test {test_num+1}/{num_tests}...")

#             # Initialize lists to hold the scores for each prompt
#             scores = {
#                 'perplexity': [],
#                 'bleu': [],
#                 'meteor': [],
#                 'distinct': [],
#                 'sentiment': []
#             }

#             # Track the time taken for each test set (5 iterations)
#             start_time = time.time()

#             # Iterate through 5 player prompts for this test
#             for player_prompt in player_prompt_list[:5]:  # First 5 player prompts
#                 full_prompt = f"{GLOBAL_SYSTEM_PROMPT}\n{local_prompt}\n{player_prompt}"
#                 print(f"[DEBUG] Full prompt for Player Prompt: {player_prompt}")

#                 # Get the model's response
#                 reply, mood = get_npc_response(player_prompt=player_prompt, local_prompt=local_prompt)

#                 # Calculate metrics for the current response
#                 perplexity_score = calculate_perplexity(reply)
#                 bleu_score = calculate_bleu(full_prompt, reply)
#                 meteor_score = calculate_meteor(full_prompt, reply)
#                 distinct_score = calculate_distinct(reply)
#                 sentiment_score = analyze_sentiment(reply)

#                 # Append the scores
#                 scores['perplexity'].append(perplexity_score)
#                 scores['bleu'].append(bleu_score)
#                 scores['meteor'].append(meteor_score)
#                 scores['distinct'].append(distinct_score)
#                 scores['sentiment'].append(sentiment_score['compound'])

#             # Calculate average scores for this test
#             avg_scores = {
#                 'perplexity': sum(scores['perplexity']) / len(scores['perplexity']),
#                 'bleu': sum(scores['bleu']) / len(scores['bleu']),
#                 'meteor': sum(scores['meteor']) / len(scores['meteor']),
#                 'distinct': sum(scores['distinct']) / len(scores['distinct']),
#                 'sentiment': sum(scores['sentiment']) / len(scores['sentiment']),
#             }

#             # Calculate the time taken for this test set
#             end_time = time.time()
#             test_set_time = end_time - start_time
#             print(f"[RESULTS] Test {test_num+1} - Average Sentiment: {avg_scores['sentiment']}")
#             print(f"[RESULTS] Test {test_num+1} - Average Perplexity: {avg_scores['perplexity']}")
#             print(f"[RESULTS] Test {test_num+1} - Average BLEU: {avg_scores['bleu']}")
#             print(f"[RESULTS] Test {test_num+1} - Average METEOR: {avg_scores['meteor']}")
#             print(f"[RESULTS] Test {test_num+1} - Average Distinct: {avg_scores['distinct']}")
#             print(f"[INFO] Time taken for this test set: {test_set_time:.2f} seconds")
#             print("="*50)

#             # Append the average scores of this test to the overall results
#             all_results.append([avg_scores['sentiment'], avg_scores['perplexity'], avg_scores['bleu'], avg_scores['meteor'], avg_scores['distinct'], test_set_time])

#         # Save the results to a CSV file after the evaluation is complete
#         save_results_to_csv(all_results)
#         print("[INFO] Results saved to 'evaluation_results.csv'")

# # Example Usage
# local_prompt_list = [
#     "You pride yourself on your courage and integrity, and you speak with confidence, but you can also show humility in the face of a worthy opponent. "
#     "You have lived through many battles and hardships, which have shaped your character. "
#     "When responding, your mood may shift according to the conversation, but you always maintain your honor and never break character. "
# ]
# player_prompt_list = [
#     "Hey there, are you the noble desert warrior everyone speaks of?",
#     "How did you get the name 'desert warrior'?",
#     "Have you faced multiple enemies in order to defend your title?",
#     "You must be a fearsome foe if you have the name 'desert warrior'",
#     "Have you ever thought of abandoning that name one day?"
# ]

# # Run the evaluation for each full prompt combination
# run_evaluation(local_prompt_list, player_prompt_list, num_tests=50)
