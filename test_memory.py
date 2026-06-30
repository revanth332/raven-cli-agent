from agent.utils import save_to_memory, save_to_project_memory, log_successful_debug, save_concept, get_current_timestamp

def test_memory_functions():
    print("--- Starting Memory Functions Test ---")
    
    # 1. Test get_current_timestamp
    timestamp = get_current_timestamp()
    print(f"Current Timestamp: {timestamp}")
    
    # 2. Test save_to_project_memory
    fact_to_save = f"[{timestamp}] - Test fact from test_memory.py script."
    print(f"\nAttempting to save fact: '{fact_to_save}'")
    result_project = save_to_project_memory(fact=fact_to_save)
    print(f"save_to_project_memory result: {result_project}")
    
    # # 3. Test save_to_memory
    # information_to_save = "User is successfully testing memory functions."
    # print(f"\nAttempting to save global memory: '{information_to_save}'")
    # result_global = save_to_memory(information=information_to_save, category="test_fact")
    # print(f"save_to_memory result: {result_global}")
    
    # 4. Test log_successful_debug
    error = "Test Error: Memory function not found."
    solution = "Implemented placeholder functions and then imported actual utils."
    print(f"\nAttempting to log debug: Error='{error}' Solution='{solution}'")
    result_debug = log_successful_debug(error_description=error, solution=solution)
    print(f"log_successful_debug result: {result_debug}")

    # 5. Test save_concept
    concept = "Test Concept"
    explanation = "This is a test explanation for the save_concept function."
    print(f"\nAttempting to save concept: '{concept}'")
    result_concept = save_concept(concept_name=concept, explanation=explanation)
    print(f"save_concept result: {result_concept}")
    
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    test_memory_functions()