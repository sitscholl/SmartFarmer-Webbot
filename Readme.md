# Introduction
This docker application contains python code to scrape the SmartFarmer and Beratungsring Websites using selenium and create an overview on the last spraying application dates for different pests combined with the days and precipitation between the respective application date and the current date.

# Usage

## Building the image
Run the following command with the current working directory set to the application:

```
docker build -t behandlungsuebersicht .
```

## Running the image

The following command can be used to run the image in shell mode. This enables to inspect the file structure and test  commands.

```
docker run --rm -it --entrypoint=/bin/bash  behandlungsuebersicht
```

However, running the application code inside the container requires some additional specifications. 
In particular, [it is important to specify the --shm-size argument](https://stackoverflow.com/questions/53902507/unknown-error-session-deleted-because-of-page-crash-from-unknown-error-cannot), otherwise the browser may crash.


```
docker run --rm -it --entrypoint=/bin/bash --shm-size=500m --mount type=bind,src="$(pwd)"/screenshots,dst=/app/screenshots behandlungsuebersicht
```

The application code also needs some secrets to be able to log into the required websites and extract the information. [Pass them via an .env file at runtime using the following syntax](https://stackoverflow.com/questions/75887571/why-does-my-docker-mount-secret-not-show-in-the-container-run-secrets):

```
docker run --rm -it --entrypoint=/bin/bash --shm-size=500m --env-file=credentials.env --mount type=bind,src="$(pwd)"/screenshots,dst=/app/screenshots behandlungsuebersicht  
```
