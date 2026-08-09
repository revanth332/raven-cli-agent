import tempfile
import os
import shutil
from pathlib import Path
from pydantic import BaseModel, Field
from google.genai import types
from agent.core.llm import get_genai_client, get_chat_session
from agent.main import run_agent_loop, console

class GraderOutput(BaseModel):
    score: int = Field(
        description="A score from 1 to 5. 5 means the bug was perfectly resolved without introducing new errors. 1 means the agent completely failed or corrupted the file."
    )
    reasoning: str = Field(
        description="Detailed, step-by-step technical explanation of why you assigned this score."
    )

EVAL_DATASET = [
    {
        "name": "Python Typo Fix",
        "file_name": "calc.py",
        "initial_content": """def add(a, b):
    # Typo: subtracting instead of adding!
    return a - b
""",
        "prompt": "Read calc.py and fix the logic typo in the add function so it actually adds.",
        "expected_behavior": "The return statement in calc.py should be changed from 'return a - b' to 'return a + b'."
    },
    {
        "name": "Unused Import Cleanup",
        "file_name": "utils.py",
        "initial_content": """import sys
import os

def greet(name):
    return f"Hello, {name}!"
""",
        "prompt": "Read utils.py and remove any unused import statements to clean up the code.",
        "expected_behavior": "Both 'import sys' and 'import os' should be completely removed because they are not used."
    },
    {"name": "Self-Healing Median Algorithm",
        "file_name": "analytics.py",
        "initial_content": """def calculate_median(numbers):
    # Bug: We completely forgot to sort the numbers list!
    # Bug: On even lengths, this integer division is incorrect.
    n = len(numbers)
    if n == 0:
        raise ValueError("List is empty")
        
    mid = n // 2
    if n % 2 == 1:
        return numbers[mid]
    else:
        return (numbers[mid - 1] + numbers[mid]) / 2
""",
        # We also create the test file inside the sandbox!
        # The prompt forces Raven to RUN the tests first.
        "prompt": "The tests in test_analytics.py are failing. Run 'python test_analytics.py' to see the failure, read analytics.py, fix the calculate_median function so it sorts the numbers first and correctly calculates the median for both odd and even lengths, then re-run the tests to verify they pass.",
        "expected_behavior": "The agent must modify calculate_median to sort the list first (e.g. sorted_nums = sorted(numbers)) and correctly calculate the median. It must verify its fix by running 'python test_analytics.py' and showing that it prints 'ALL_TESTS_PASSED'.",
        # Extra setup: We need to write TWO files to the sandbox for this test!
        "extra_files": {
            "test_analytics.py": """import sys
from analytics import calculate_median

try:
    # Odd length unsorted list: sorted is [1, 2, 3] -> median is 2
    assert calculate_median([3, 1, 2]) == 2, f"Failed odd unsorted: got {calculate_median([3, 1, 2])}"
    
    # Even length unsorted list: sorted is [1, 2, 3, 4] -> median is 2.5
    assert calculate_median([4, 1, 3, 2]) == 2.5, f"Failed even unsorted: got {calculate_median([4, 1, 3, 2])}"
    
    print("ALL_TESTS_PASSED")
    sys.exit(0)
except AssertionError as e:
    print(f"TEST_FAILED: {e}")
    sys.exit(1)
"""
        }
    }
]

# --- THE AI JUDGE ---
def grade_result(original: str, modified: str, expected: str) -> GraderOutput:
    """Uses Gemini as a Judge to evaluate the patch, enforcing a strict Pydantic output schema."""
    client = get_genai_client()
    
    prompt = f"""You are a senior code reviewer grading an autonomous junior developer agent.
    Evaluate the code changes made by the agent.

    ORIGINAL CODE:
    ```python
    {original}

    MODIFIED CODE AFTER AGENT EDIT:
    ```python
    {modified}

    EXPECTED BEHAVIOR:
    {expected}

    Grading Rubric:
    5: Perfect fix, matches expected behavior exactly, no syntax errors.
    4: Functional fix, but left unnecessary whitespace or minor styling issues.
    3: Attempted the fix, but left syntax errors or only partially resolved the issue.
    1-2: Failed, broke the code, or completely corrupted the file.
    """
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GraderOutput,
        system_instruction=types.Part.from_text(text="You are a strict, objective, and fair senior software engineer grading code changes.")
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=config
    )
    return GraderOutput.model_validate_json(response.text)

def run_eval_suite():
    """Runs Raven autonomously against the test dataset and prints the scorecard."""
    console.rule("[bold cyan] RAVEN AUTONOMOUS EVALUATION SUITE [/bold cyan]")

    scores = []

    for case in EVAL_DATASET:
        console.print(f"\n[bold yellow]Starting Test Case: '{case['name']}'[/bold yellow]")
        with tempfile.TemporaryDirectory() as sandbox_dir:
            original_dir = os.getcwd()
            os.chdir(sandbox_dir)

            try:
                test_file = Path(case['file_name'])
                test_file.write_text(case['initial_content'],encoding='utf-8')
                if case.get("extra_files",None):
                    for name,content in case['extra_files'].items():
                        extra_file = Path(name)
                        extra_file.write_text(content,encoding='utf-8')

                chat_session = get_chat_session()

                console.print(f"[dim]Prompting Raven: '{case['prompt']}'[/dim]")
                run_agent_loop(chat_session=chat_session,intial_input=case['prompt'])

                modified_content = test_file.read_text(encoding='utf-8')

                console.print("[dim]Submitting results to Senior AI Judge...[/dim]")
                grade = grade_result(
                    original=case['initial_content'],
                    modified=modified_content,
                    expected=case['expected_behavior']
                )

                color = "green" if grade.score >= 4 else "red"
                console.print(f"[{color}]Score: {grade.score}/5[/{color}]")
                console.print(f"[dim]Judge Reasoning: {grade.reasoning}[/dim]")
                scores.append(grade.score)
            finally:
                # Always restore our working directory
                os.chdir(original_dir)

    console.rule("[bold cyan]SCORECARD SUMMARY[/bold cyan]")
    if scores:
        average = sum(scores) / len(scores)
        console.print(f"\n[bold green]Final Average Score: {average:.2f}/5[/bold green]\n")