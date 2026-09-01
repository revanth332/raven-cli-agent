- Get the current timestamp using `get_current_timestamp` tool.
- Use the git commnds :
  - To get the all local banch commit messages:
    git log --branches --author=<author_name> --since=<time_span> --pretty=format:"%h - %an, %ad : %s" --date=short -n <number_of_commits>
  - To get the all local banch commit messages with all the file changes:
    git log -p --branches --author=<author_name> --since=<time_span> --pretty=format:"%h - %an, %ad : %s" --date=short -n <number_of_commits> (Use this command only when commit messages are not sufficient to create the report accurately.)

- Based on the data you get extract the work that is done within the time period : <time_period> by comparing timestamps.
- AVOID using backticks.
- Use italic or bold styles to highlight.
- Refer the following example.
  EXAMPLE:
  Key Contributions/Work Done: Resolved lint errors and updated end-to-end test scripts to support smooth deployments. Added a Region column to the environment field in the GCP project intake form, allowing users to specify different regions for each deployment environment.
  Remarks/Risks/Dependencies: N/A
  Accomplishments/Highlights: Enhanced the GCP project intake form to support region-specific deployment configuration.
  Business Impact: Improved deployment readiness and enabled more flexible regional configuration for GCP environments.

Note:

1. If time period is not mentioned asl the user to provide the time period.
2. If you are not sure about the exact author name, ask the user.
3. Use 'n' value as increments of 5. Meaning fetch last 5, if you go out of the time span then stop and create report. other wise extract next 5 commits and so on.
