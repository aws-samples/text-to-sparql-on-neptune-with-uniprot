# sparql-generation

## Prerequisites

In order to run the code in this repository, you have three choices: you can run it in a Sagemaker Studio notebook, in a Sagemaker non-Studio notebook, or in a non-Sagemaker environment.

### Installation as a Sagemaker Studio notebook

@todo@

### Installation as a Sagemaker non-Studio notebook


Follow the following steps:

1. [Install](https://python-poetry.org/docs/) Poetry
2. Clone this repo: `git clone git@ssh.gitlab.aws.dev:simongh/sparql-generation.git` @todo@ change this
3. Change directory to the root of this repo: `cd sparql-generation` @todo@ change this
4. Install the required Python packages and create a new virtual environment: `poetry install`
5. Switch to this virtual environment: `poetry shell`
6. `python -m ipykernel install --user --name=sparql-generation-kernel`
9. Delete the cell in the notebook that looks like this:
```
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```
10. Create a new notebook and choose the newly-created kernel.

### Installation in a non-Sagemaker environment

Follow the following steps:

1. [Install](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation) pyenv
2. Use pyenv to install Python 3.11.4: `pyenv install 3.11.4`. Note that the code here might work on other versions of Python but has only been tested on this version.
3. Tell pyenv to use this version of Python: `pyenv local 3.11.4`
4. [Install](https://python-poetry.org/docs/) Poetry
5. Clone this repo: `git clone git@ssh.gitlab.aws.dev:simongh/sparql-generation.git` @todo@ change this
6. Change directory to the root of this repo: `cd sparql-generation` @todo@ change this
7. Install the required Python packages and create a new virtual environment: `poetry install`
8. Switch to this virtual environment: `poetry shell`
9. Set up the environment variables to authenticate with AWS:
```
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
```
10. Start the Jupyter server: `jupyter lab`

## Installing Uniprot

@todo@


