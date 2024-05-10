
import docker

def run_task(image):
    # BUG: Resource leak - docker client not closed
    client = docker.from_env()
    return client.containers.run(image, detach=True)
