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

if os.name == 'nt':
    ssh_key_path = r"C:\Users\adminuser\.ssh\mminichino-default-key-pair.pem"
else:
    ssh_key_path = r"/Users/michael/.ssh/mminichino-default-key-pair.pem"


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


def expand_ranges(text):
    range_list = []
    for i in text.split(','):
        if '-' not in i:
            range_list.append(int(i))
        else:
            l, h = map(int, i.split('-'))
            range_list += range(l, h+1)
    return range_list


def create_port_dict(port_list: List[int]):
    result = {}
    for port in port_list:
        key = f"{port}/tcp"
        result.update({key: port})
    return result


def start_container(image: str,
                    name: str,
                    volume_mount: Union[str, None] = None,
                    dir_mount: Union[str, None] = None,
                    platform: Union[str, None] = None,
                    ports: Union[str, None] = None,
                    command: Union[str, list, None] = None) -> Container:
    if not platform:
        platform = f"linux/{os.uname().machine}"
    if not ports:
        ports = "80,443"
    docker_api = APIClient(base_url='unix://var/run/docker.sock')
    client = docker.from_env()
    client.images.prune()
    client.containers.prune()
    client.networks.prune()
    client.volumes.prune()
    docker_api.prune_builds()
    volume_map = None

    port_struct = create_port_dict(expand_ranges(ports))

    print(f"Starting {image} container")

    try:
        if volume_mount and not dir_mount:
            volume = client.volumes.create(name=f"{name}-vol", driver="local", driver_opts={"type": "tmpfs", "device": "tmpfs", "o": "size=2048m"})
            volume_map = [f"{volume.name}:{volume_mount}"]
        elif dir_mount:
            if not volume_mount:
                volume_mount = dir_mount
            volume_map = [f"{dir_mount}:{volume_mount}"]
        container_id = client.containers.run(image,
                                             tty=True,
                                             detach=True,
                                             platform=platform,
                                             name=name,
                                             ports=port_struct,
                                             volumes=volume_map,
                                             command=command
                                             )
    except docker.errors.APIError as e:
        if e.status_code == 409:
            container_id = client.containers.get(name)
        else:
            raise

    print("Container started")
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


def run_in_container(name: str, command: Union[str, List[str]], directory: Union[str, None] = None):
    container_id = get_container_id(name)
    print(f"Running: {command}")
    exit_code, output = container_id.exec_run(command, workdir=directory)
    for line in output.split(b'\n'):
        if len(line) > 0:
            print(line.decode("utf-8"))
    assert exit_code == 0


def get_container_id(name: str) -> Union[Container, None]:
    client = docker.from_env()
    try:
        return client.containers.get(name)
    except docker.errors.NotFound:
        return None


def get_container_ip(name: str):
    container_id = get_container_id(name)
    try:
        return container_id.attrs['NetworkSettings']['IPAddress']
    except KeyError:
        return None


def get_container_binds(name: str):
    binds = []
    container_id = get_container_id(name)
    mounts = container_id.attrs.get('Mounts', [])
    for mount in mounts:
        m_type = mount.get('Type')
        if m_type == 'bind':
            binds.append(mount.get('Source'))
    return binds


def stop_container(name: str):
    container_id = get_container_id(name)
    if not container_id:
        return
    client = docker.from_env()
    print("Stopping container")
    container_id.stop()
    print("Removing test container")
    container_id.remove()
    try:
        volume = client.volumes.get(f"{name}-vol")
        volume.remove()
    except docker.errors.NotFound:
        pass
    print("Done.")
