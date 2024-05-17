
import docker

def run_task(image):
    # FIX: Ensure docker client is closed after use
    with docker.from_env() as client:
        return client.containers.run(image, detach=True)
