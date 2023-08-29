##

import docker
from docker.errors import APIError
from docker.models.containers import Container
from docker import APIClient
from typing import Union, List
from io import BytesIO
import io
import os
import tarfile
import warnings
import logging
import subprocess

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
logging.getLogger("docker").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def make_local_dir(name: str):
    if not os.path.exists(name):
        path_dir = os.path.dirname(name)
        if not os.path.exists(path_dir):
            make_local_dir(path_dir)
        try:
            os.mkdir(name)
        except OSError:
            raise


def cmd_exec(command: Union[str, List[str]], directory: str):
    buffer = io.BytesIO()

    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=directory)

    while True:
        data = p.stdout.read()
        if not data:
            break
        buffer.write(data)

    p.communicate()

    if p.returncode != 0:
        raise ValueError("command exited with non-zero return code")

    buffer.seek(0)
    return buffer


def copy_to_container(container_id: Container, src: str, dst: str):
    print(f"Copying {src} to {dst}")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as tar, open(src, 'rb') as file:
        info = tar.gettarinfo(fileobj=file)
        info.name = os.path.basename(src)
        tar.addfile(info, file)

    container_id.put_archive(dst, stream.getvalue())


def copy_log_from_container(container_id: Container, src: str, directory: str):
    make_local_dir(directory)
    src_base = os.path.basename(src)
    dst = f"{directory}/{src_base}"
    print(f"Copying {src} to {dst}")
    try:
        bits, stat = container_id.get_archive(src)
    except docker.errors.NotFound:
        print(f"{src}: not found")
        return
    stream = io.BytesIO()
    for chunk in bits:
        stream.write(chunk)
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode='r') as tar, open(dst, 'wb') as file:
        f = tar.extractfile(src_base)
        data = f.read()
        file.write(data)


def copy_dir_to_container(container_id: Container, src_dir: str, dst: str):
    print(f"Copying {src_dir} to {dst}")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as tar:
        name = os.path.basename(src_dir)
        tar.add(src_dir, arcname=name, recursive=True)

    container_id.put_archive(dst, stream.getvalue())


def copy_git_to_container(container_id: Container, src: str, dst: str):
    container_mkdir(container_id, dst)
    file_list = []
    print(f"Copying git HEAD to {dst}")
    output: BytesIO = cmd_exec(["git", "ls-tree", "--full-tree", "--name-only", "-r", "HEAD"], src)
    while True:
        line = output.readline()
        if not line:
            break
        line_string = line.decode("utf-8")
        file_list.append(line_string.strip())
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as tar:
        for filename in file_list:
            tar.add(filename, recursive=True)

    container_id.put_archive(dst, stream.getvalue())


def container_mkdir(container_id: Container, directory: str):
    command = ["mkdir", "-p", directory]
    exit_code, output = container_id.exec_run(command)
    assert exit_code == 0


def start_container(image: str, platform: str = "linux/amd64", volume_mount: str = "/opt") -> Container:
    docker_api = APIClient(base_url='unix://var/run/docker.sock')
    client = docker.from_env()
    client.images.prune()
    client.containers.prune()
    client.networks.prune()
    client.volumes.prune()
    docker_api.prune_builds()

    print(f"Starting {image} container")

    try:
        volume = client.volumes.create(name="pytest-volume", driver="local", driver_opts={"type": "tmpfs", "device": "tmpfs", "o": "size=2048m"})
        container_id = client.containers.run(image,
                                             tty=True,
                                             detach=True,
                                             privileged=True,
                                             platform=platform,
                                             name="pytest",
                                             ports={'8091/tcp': 8091},
                                             security_opt=["seccomp=unconfined", "apparmor=unconfined"],
                                             volumes=[f"{volume.name}:{volume_mount}"],
                                             command=["/usr/sbin/init"]
                                             )
    except docker.errors.APIError as e:
        if e.status_code == 409:
            container_id = client.containers.get('pytest')
        else:
            raise

    print("Container started")
    print("Done.")
    return container_id


def image_name(container_id: Container):
    tags = container_id.image.tags
    return tags[0].split(':')[0].replace('/', '-')


def container_log(container_id: Container, directory: str):
    make_local_dir(directory)
    print(f"Copying {container_id.name} log to {directory}")
    filename = f"{directory}/{container_id.name}.log"
    output = container_id.attach(stdout=True, stderr=True, logs=True)
    with open(filename, 'w') as out_file:
        out_file.write(output.decode("utf-8"))
        out_file.close()


def run_in_container(container_id: Container, directory: str, command: Union[str, List[str]]):
    print(f"Running: {command if type(command) == str else ' '.join(command)}")
    exit_code, output = container_id.exec_run(command, workdir=directory)
    for line in output.split(b'\n'):
        if len(line) > 0:
            print(line.decode("utf-8"))
    assert exit_code == 0
    print("Done.")


def get_container_id(name: str = "pytest"):
    client = docker.from_env()
    try:
        return client.containers.get(name)
    except docker.errors.NotFound:
        return None


def stop_container(container_id: Container):
    client = docker.from_env()
    print("Stopping container")
    container_id.stop()
    print("Removing test container")
    container_id.remove()
    try:
        volume = client.volumes.get("pytest-volume")
        volume._remove()
    except docker.errors.NotFound:
        pass
    print("Done.")
