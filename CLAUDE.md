Documentation:'
- Put all of our core documents, learnings underneath a `docs` folder in the root of the project
- `/docs/ideas` is where future ideas are written down. Sample existing docs in their for the format.
- use markdown to write documentation
- README.md is the main entrypoint for the project. It should contain:
    - a high level overview of the project
    - a good blurb on why this project exists
    - what we've done so far
    - what we're doing next

Coding:
- Use python as the core programming language.
- Use uv as the python package manager.
- Keep all python code unerneath the `code` directory. Ensure `uv` respects this.
- Use python 3.14 (pi) as the version
- Prefer flatter projects over nested ones. Use separate files instead of nested folders to keep it simple
- Use python3 typehints for everything.
- Use pydantic for storing key datastructures in the project and for adding validation
- keep docstrings succinct and to the point.
- use pathlib instead of the os.path module
- When running code use `uv run <script>.py`
- I prefer functional patterns. For example, if you execute a series of async functions, instead of passing in a data structure modifying function, I'd prefer you to return the data structure from the function and aggregate the results.
- When running a dataprocessing script, use these patterns:
    - Always provide user-friendly output with the status of the job. The number of successful and failed operations
    - Provide an ETA of the job completion.
    - Always use multiprocessing for compute heavy operations or threading for IO heavy operations.
    - Always keep track of the succ/failures in a single manifest file.
    - Persist a manifest file periodically so I can keep track of the jobs progress

# frontend
- keep all frontend code under the `frontend` directory
- use nextjs for the frontend
- Download the graph data in the frontend app and then use clientside code to load and manipulate it.