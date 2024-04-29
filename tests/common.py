##

import docker
from docker.errors import APIError
from docker.models.containers import Container
from docker import APIClient
from typing import Union, List
from io import BytesIO
from pathlib import Path
from Crypto.Cipher import AES
from Crypto import Random
from hashlib import sha256
import string
import random
import base64
import hashlib
import io
import os
import tarfile
import warnings
import logging
import subprocess

warnings.filterwarnings("ignore")
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
logger = logging.getLogger('tests.common')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

ssh_key_path = os.path.join(Path.home(), '.ssh', 'pytest-key-pair.pem')
ssh_pub_key_path = os.path.join(Path.home(), '.ssh', 'pytest-key-pair.pub')
ssh_key_relative_path = os.path.relpath(ssh_key_path, Path.home())
ssh_pub_key_relative_path = os.path.relpath(ssh_pub_key_path, Path.home())
capella_config_path = os.path.join(Path.home(), '.capella')
capella_config_relative_path = os.path.relpath(capella_config_path, Path.home())
aws_config_dir = os.path.join(Path.home(), '.aws')
gcp_config_dir = os.path.join(Path.home(), '.config', 'gcloud')
azure_config_dir = os.path.join(Path.home(), '.azure')
linux_image_name = "ubuntu:jammy"


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


def cli_run(cmd: str, *args: str, input_file: str = None):
    command_output = ""
    run_cmd = [
        cmd,
        *args
    ]

    p = subprocess.Popen(run_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    if input_file:
        with open(input_file, 'rb') as input_data:
            while True:
                line = input_data.readline()
                if not line:
                    break
                p.stdin.write(line)
            p.stdin.close()

    while True:
        line = p.stdout.readline()
        if not line:
            break
        line_string = line.decode("utf-8")
        command_output += line_string

    p.wait()

    return p.returncode, command_output


def set_root(tarinfo, uid=0, gid=0, uname="root", gname="root"):
    tarinfo.uid = uid
    tarinfo.gid = gid
    tarinfo.uname = uname
    tarinfo.gname = gname
    return tarinfo


def random_string(n=32):
    return ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=n))


def encrypt_file(file_name: str, key_text: str):
    with open(file_name, "rb") as in_file:
        raw = in_file.read()
        digest = sha256(raw).digest()
    in_bytes = bytearray()
    in_bytes.extend(digest)
    in_bytes.extend(raw)
    output_file = file_name + ".enc"
    iv = Random.new().read(AES.block_size)
    bs = AES.block_size
    key = hashlib.sha256(key_text.encode()).digest()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    block = in_bytes + (bs - len(in_bytes) % bs) * chr(bs - len(in_bytes) % bs).encode()
    result = base64.b64encode(iv + cipher.encrypt(block)).decode("utf-8")
    with open(output_file, "w") as out_file:
        out_file.write(result)
        out_file.write("\n")


def decrypt_file(file_name: str, key_text: str):
    with open(file_name, "r") as in_file:
        enc = in_file.read()
    data = base64.b64decode(enc)
    iv = data[:AES.block_size]
    key = hashlib.sha256(key_text.encode()).digest()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    block = cipher.decrypt(data[AES.block_size:])
    result = block[:-ord(block[len(block) - 1:])]
    digest = result[0:32]
    raw = result[32:]
    check = sha256(raw).digest()
    if check != digest:
        raise ValueError("can not decrypt: checksum mismatch: check that the key is correct")
    path = os.path.dirname(file_name)
    output_file = os.path.join(path, Path(file_name).stem)
    with open(output_file, "wb") as out_file:
        out_file.write(raw)


def create_cred_package(file_name: str):
    with tarfile.open(file_name, mode='w:gz') as tar:
        tar.add(ssh_key_path, arcname=ssh_key_relative_path)
        tar.add(ssh_pub_key_path, arcname=ssh_pub_key_relative_path)
        tar.add(capella_config_path, arcname=capella_config_relative_path, recursive=True)
        tar.add(aws_config_dir, arcname=os.path.relpath(aws_config_dir, Path.home()), recursive=True)
        tar.add(gcp_config_dir, arcname=os.path.relpath(gcp_config_dir, Path.home()), recursive=True)
        tar.add(azure_config_dir, arcname=os.path.relpath(azure_config_dir, Path.home()), recursive=True)


def copy_home_env_to_container(container_id: Container, dst: str, uid=0, gid=0, uname="root", gname="root"):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w|') as tar:
        tar.add(ssh_key_path, arcname=ssh_key_relative_path, filter=lambda x: set_root(x, uid, gid, uname, gname))
        tar.add(capella_config_path, arcname=capella_config_relative_path, recursive=True, filter=lambda x: set_root(x, uid, gid, uname, gname))
        tar.add(aws_config_dir, arcname=os.path.relpath(aws_config_dir, Path.home()), recursive=True, filter=lambda x: set_root(x, uid, gid, uname, gname))
        tar.add(gcp_config_dir, arcname=os.path.relpath(gcp_config_dir, Path.home()), recursive=True, filter=lambda x: set_root(x, uid, gid, uname, gname))
        tar.add(azure_config_dir, arcname=os.path.relpath(azure_config_dir, Path.home()), recursive=True, filter=lambda x: set_root(x, uid, gid, uname, gname))

    container_id.put_archive(dst, stream.getvalue())


def copy_to_container(container_id: Container, src: str, dst: str):
    logger.info(f"Copying {src} to {dst}")
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
                    dir_mount: Union[str, List[dict], None] = None,
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

    logger.info(f"Starting {image} container")

    try:
        if volume_mount and not dir_mount:
            volume = client.volumes.create(name=f"{name}-vol", driver="local", driver_opts={"type": "tmpfs", "device": "tmpfs", "o": "size=2048m"})
            volume_map = [f"{volume.name}:{volume_mount}"]
        elif dir_mount:
            if not volume_mount:
                volume_mount = dir_mount
            if type(dir_mount) is str:
                volume_map = [f"{dir_mount}:{volume_mount}"]
            elif type(dir_mount) is list:
                volume_map = dir_mount
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

    logger.info("Container started")
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


def run_in_container(container_id: Container, command: Union[str, List[str]], directory: Union[str, None] = None, environment: Union[dict, None] = None):
    exit_code, output = container_id.exec_run(command, workdir=directory, environment=environment)
    for line in output.split(b'\n'):
        if len(line) > 0:
            logger.info(line.decode("utf-8"))
    if exit_code == 0:
        return True
    else:
        return False


def get_cmd_output(container_id: Container, command: Union[str, List[str]], directory: Union[str, None] = None, environment: Union[dict, None] = None):
    exit_code, output = container_id.exec_run(command, workdir=directory, environment=environment)
    return exit_code, output.decode("utf-8")


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
