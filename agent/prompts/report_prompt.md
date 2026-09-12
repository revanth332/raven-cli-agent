- Target time period for this report: <time_period>
- Get the current timestamp using `get_current_timestamp` tool.

1. Author Identification:
   - Auto-detect the author name by running `git config user.name` via `execute_command`.
   - If not set or empty, check the author of the most recent commit: `git log -1 --pretty=format:"%an"` via `execute_command`.
   - Use the detected author name in the `get_git_log` tool call. Do not pause to ask the user for author unless auto-detection yields no name.

2. Commit History Retrieval:
   - Preferred Method: Use the dedicated `get_git_log` tool to retrieve commits within the target time period.
     - Convert <time_period> into the `since` argument (e.g. "past 7 days" or "week" -> "7 days ago", "2 weeks" -> "2 weeks ago", "month" -> "1 month ago"). Default is "7 days ago".
     - Pass `author="<author_name>"`, `since="<since_val>"`, and `include_stat=True`.
     - `get_git_log` automatically excludes lockfiles, minified files, and build outputs to keep context compact.
   - If running manual git commands, include `--stat` and exclude lockfiles.
   - CRITICAL CONSTRAINT: DO NOT use `git log -p` or `--patch` across commits. Dumping raw diffs exhausts context tokens.
   - If a specific commit requires deeper inspection, inspect ONLY that specific commit targeting specific files:
     git show <commit_hash> --stat
     or
     git show <commit_hash> -- <file_path>

3. Report Generation:
   - Based on the commit messages and file change stats within <time_period>, synthesize a professional, concise report.
   - AVOID using backticks.
   - Use italic or bold styles to highlight.
   - Follow this exact structure:

   Key Contributions/Work Done: <Summary of core changes and work items completed>
   Remarks/Risks/Dependencies: <Any risks, dependencies, blockers, or N/A>
   Accomplishments/Highlights: <Key milestones, architectural improvements, or critical fixes>
   Business Impact: <Impact on stability, performance, developer velocity, or system readiness>

   EXAMPLE:
   Key Contributions/Work Done: Resolved lint errors and updated end-to-end test scripts to support smooth deployments. Added a Region column to the environment field in the GCP project intake form, allowing users to specify different regions for each deployment environment.
   Remarks/Risks/Dependencies: N/A
   Accomplishments/Highlights: Enhanced the GCP project intake form to support region-specific deployment configuration.
   Business Impact: Improved deployment readiness and enabled more flexible regional configuration for GCP environments.

