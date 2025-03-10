# Introduction
This docker application contains python code to scrape the SmartFarmer and Beratungsring Websites using selenium and create an overview on the last spraying application dates for different pests combined with the days and precipitation between the respective application date and the current date.

# Usage

## Building the image
Run the following command with the current working directory set to the application:

```
docker build -t spritzintervall .
```

## Running the image

The following command can be used to run the image in shell mode. This enables to inspect the file structure and test  commands.

```
docker run --rm -it --entrypoint=/bin/bash spritzintervall
```

However, running the application code inside the container requires some additional specifications. 
In particular, [it is important to specify the --shm-size argument](https://stackoverflow.com/questions/53902507/unknown-error-session-deleted-because-of-page-crash-from-unknown-error-cannot), otherwise the browser may crash.


```
docker run --rm -it --entrypoint=/bin/bash --shm-size=500m spritzintervall
```

The application code also needs some secrets to be able to log into the required websites and extract the information. [Pass them via an .env file at runtime using the following syntax](https://stackoverflow.com/questions/75887571/why-does-my-docker-mount-secret-not-show-in-the-container-run-secrets):

```
docker run --rm -it --entrypoint=/bin/bash --shm-size=500m --env-file=credentials.env spritzintervall  
```

## Hosting on Google Cloud Run

### Set up project

The first step is to create a google cloud project at the [google cloud console](https://console.cloud.google.com/). Ensure that billing is enabled for the project, as this is required to use google cloud run (can be activated by going to the google cloud run page).

Also enable the Artifact Registry for the project at [this link](https://console.cloud.google.com/flows/enableapi?apiid=artifactregistry.googleapis.com&redirect=https://cloud.google.com/artifact-registry/docs/docker/quickstart)

### Push local docker container to artifact registry

The next steps can either be followed by downloading the gcloud sdk or by using the terminal within the google cloud console. The second approach will be described here. First, create a new repository within the artifact registriy, where the docker image will be stored:

```
gcloud artifacts repositories create spritzintervall \
  --repository-format=docker \
  --location=europe \
  --description="Spritzintervall Docker App"
```

Next, configure docker to use the glcoud credentials. This command updates your Docker configuration to use Google Cloud’s credential helper for Artifact Registry. If the docker image is developed locally, the following command has to be run in the local shell and required a working installation of the google cloud sdk (see below):

```
gcloud auth configure-docker europe-docker.pkg.dev
```

The local Docker image must be tagged to match the Artifact Registry repository naming convention:

```
LOCATION-docker.pkg.dev/PROJECT_ID/REPOSITORY_NAME/IMAGE:TAG
```

To do this, run:

```
docker tag spritzintervall:latest europe-docker.pkg.dev/oberlenghof/spritzintervall/spritzintervall:latest
```

Now push the tagged image to the artifact registry:

```
docker push europe-docker.pkg.dev/oberlenghof/spritzintervall/spritzintervall:latest
```

You can verify the upload in the Google Cloud Console under Artifact Registry or by listing images using:

```
gcloud artifacts docker images list europe-docker.pkg.dev/oberlenghof/spritzintervall
```

### Deploy to google cloud run

A script that should be exectued at regular intervals is best deployed as a job to google cloud run. First, enable the necessary services in the google cloud console for the project:

```
gcloud services enable artifactregistry.googleapis.com \
                      run.googleapis.com \
                      cloudbuild.googleapis.com \
                      logging.googleapis.com
```

The container can then be deployed to google cloud run using the web interface: Go to google cloud run in the project and select add job and fill out the requested fields. Make sure to specify an adequate memory limit. If you are using secrets, make sure to add them via the [secret manager](https://console.cloud.google.com/security/secret-manager). After adding them, follow the following steps to add the necessary permissions to the service account so that the secrets can be acessed:

1. Navigate to IAM & Admin:

- Open the Google Cloud Console.
- Go to IAM & Admin > IAM.
- Find the Service Account

2. Edit Permissions:

- Click the pencil icon next to the service account.
- Click + Add Another Role.
- In the role dropdown, select secrets manager secrets acessor. If you want to set up a regular trigger via cronjob to launch the job, also add the Cloud Run Invoker role here.
- Save your changes.

Finally, a regular trigger can be set up using the web interface.

## Installing gcloud sdk

To download and install the gcloud sdk, the following steps must be followed. 

Insert the following command in Powershell (administrator mode): 

```
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")
& $env:Temp\GoogleCloudSDKInstaller.exe
```

After the installation has been finished, a window appears where gcloud sdk can be configured and the project to be used can be set. Otherwise, this can also be done manually via the command `gcloud init`. 