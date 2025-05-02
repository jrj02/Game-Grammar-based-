from llama_cpp import Llama
from os.path import join
import math

model_path = join("models", "mistral", "mistral-7b-instruct-v0.1.Q4_K_M.gguf")
llm = Llama(model_path=model_path, n_ctx=2048, n_threads=6)

def calculate_perplexity(text):
    try:
        # Get the model's output
        output = llm(text)
        print("[DEBUG] Model Output:", output)

        # Check if the model provides any relevant data for perplexity (e.g., completion_tokens, logprobs)
        completion_tokens = output.get('usage', {}).get('completion_tokens', 0)
        if completion_tokens == 0:
            print("[ERROR] No tokens found in model output.")
            return float('inf')

        # Simplified perplexity using text length and token count
        perplexity = math.exp(completion_tokens / len(text.split()))  # Approximation using text length and token count

        return perplexity
    except Exception as e:
        print(f"[ERROR] Error in calculating perplexity: {e}")
        return float('inf')  # Return a high value if there's an error in calculation

def evaluate_perplexity(npc_response, player_input, npc_context):
    #Function to evaluate the perplexity of the generated NPC dialogue in the background.
    
    perplexity = calculate_perplexity(npc_response)
    # Log or store the results for analysis (could be a log file or database)
    print(f"Perplexity for response: {perplexity}")
    return perplexity