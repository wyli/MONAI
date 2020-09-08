# Copyright 2020 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import logging
import os
import shutil
import tarfile
import zipfile
from typing import Optional
from urllib.error import ContentTooShortError, HTTPError, URLError
from urllib.request import Request, urlopen, urlretrieve

from monai.utils import optional_import, progress_bar

gdown, has_gdown = optional_import("gdown", "3.6")


def check_hash(filepath: str, val: Optional[str] = None, hash_type: str = "md5") -> bool:
    """
    Verify hash signature of specified file.

    Args:
        filepath: path of source file to verify hash value.
        val: expected hash value of the file.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.

    """
    if val is None:
        print(f"Expected {hash_type} is None, skip {hash_type} check for file {filepath}.")
        return True
    if hash_type.lower() == "md5":
        actual_hash = hashlib.md5()
    elif hash_type.lower() == "sha1":
        actual_hash = hashlib.sha1()
    else:
        raise NotImplementedError(f"Unknown 'hash_type' {hash_type}.")
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                actual_hash.update(chunk)
    except Exception as e:
        print(f"Exception in check_hash: {e}")
        return False
    if val != actual_hash.hexdigest():
        print("check_hash failed.")
        return False

    print(f"Verified '{os.path.basename(filepath)}', {hash_type}: {val}.")
    return True


def download_url(url: str, filepath: str, hash_val: Optional[str] = None, hash_type: str = "md5") -> None:
    """
    Download file from specified URL link, support process bar and hash check.

    Args:
        url: source URL link to download file.
        filepath: target filepath to save the downloaded file.
        hash_val: expected hash value to validate the downloaded file.
            if None, skip hash validation.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.

    Raises:
        RuntimeError: When the hash validation of the ``filepath`` existing file fails.
        RuntimeError: When a network issue or denied permission prevents the
            file download from ``url`` to ``filepath``.
        URLError: See urllib.request.urlretrieve.
        HTTPError: See urllib.request.urlretrieve.
        ContentTooShortError: See urllib.request.urlretrieve.
        IOError: See urllib.request.urlretrieve.
        RuntimeError: When the hash validation of the ``url`` downloaded file fails.

    """
    if os.path.exists(filepath):
        if not check_hash(filepath, hash_val, hash_type):
            raise RuntimeError(
                f"{hash_type} check of existing file failed: filepath={filepath}, expected {hash_type}={hash_val}."
            )
        print(f"file {filepath} exists, skip downloading.")
        return

    if url.startswith("https://drive.google.com"):
        if not has_gdown:
            raise RuntimeError("To download files from Google Drive, please install the gdown dependency.")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        gdown.download(url, filepath, quiet=False)
        if not os.path.exists(filepath):
            raise RuntimeError(
                f"Download of file from {url} to {filepath} failed due to network issue or denied permission."
            )
    elif url.startswith("https://msd-for-monai.s3-us-west-2.amazonaws.com"):
        block_size = 1024 * 1024
        tmp_file_path = filepath + ".part"
        first_byte = os.path.getsize(tmp_file_path) if os.path.exists(tmp_file_path) else 0
        file_size = -1

        try:
            file_size = int(urlopen(url).info().get("Content-Length", -1))
            progress_bar(index=first_byte, count=file_size)

            while first_byte < file_size:
                last_byte = first_byte + block_size if first_byte + block_size < file_size else file_size - 1

                req = Request(url)
                req.headers["Range"] = "bytes=%s-%s" % (first_byte, last_byte)
                data_chunk = urlopen(req, timeout=10).read()
                with open(tmp_file_path, "ab") as f:
                    f.write(data_chunk)
                progress_bar(index=last_byte, count=file_size)
                first_byte = last_byte + 1
        except IOError as e:
            logging.debug("IO Error - %s" % e)
        finally:
            if file_size == os.path.getsize(tmp_file_path):
                if hash_val and not check_hash(tmp_file_path, hash_val, hash_type):
                    raise Exception(f"Error validating the file against its {hash_type} hash")
                shutil.move(tmp_file_path, filepath)
            elif file_size == -1:
                raise Exception("Error getting Content-Length from server: %s" % url)
    else:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        def _process_hook(blocknum: int, blocksize: int, totalsize: int):
            progress_bar(blocknum * blocksize, totalsize, f"Downloading {filepath.split('/')[-1]}:")

        try:
            urlretrieve(url, filepath, reporthook=_process_hook)
            print(f"\ndownloaded file: {filepath}.")
        except (URLError, HTTPError, ContentTooShortError, IOError) as e:
            print(f"download failed from {url} to {filepath}.")
            raise e

    if not check_hash(filepath, hash_val, hash_type):
        raise RuntimeError(
            f"{hash_type} check of downloaded file failed: URL={url}, "
            f"filepath={filepath}, expected {hash_type}={hash_val}."
        )


def extractall(filepath: str, output_dir: str, hash_val: Optional[str] = None, hash_type: str = "md5") -> None:
    """
    Extract file to the output directory.
    Expected file types are: `zip`, `tar.gz` and `tar`.

    Args:
        filepath: the file path of compressed file.
        output_dir: target directory to save extracted files.
        hash_val: expected hash value to validate the compressed file.
            if None, skip hash validation.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.

    Raises:
        RuntimeError: When the hash validation of the ``filepath`` compressed file fails.
        ValueError: When the ``filepath`` file extension is not one of [zip", "tar.gz", "tar"].

    """
    target_file = os.path.join(output_dir, os.path.basename(filepath).split(".")[0])
    if os.path.exists(target_file):
        print(f"extracted file {target_file} exists, skip extracting.")
        return
    if not check_hash(filepath, hash_val, hash_type):
        raise RuntimeError(
            f"{hash_type} check of compressed file failed: " f"filepath={filepath}, expected {hash_type}={hash_val}."
        )

    if filepath.endswith("zip"):
        zip_file = zipfile.ZipFile(filepath)
        zip_file.extractall(output_dir)
        zip_file.close()
    elif filepath.endswith("tar") or filepath.endswith("tar.gz"):
        tar_file = tarfile.open(filepath)
        tar_file.extractall(output_dir)
        tar_file.close()
    else:
        raise ValueError('Unsupported file extension, available options are: ["zip", "tar.gz", "tar"].')


def download_and_extract(
    url: str, filepath: str, output_dir: str, hash_val: Optional[str] = None, hash_type: str = "md5"
) -> None:
    """
    Download file from URL and extract it to the output directory.

    Args:
        url: source URL link to download file.
        filepath: the file path of compressed file.
        output_dir: target directory to save extracted files.
            default is None to save in current directory.
        hash_val: expected hash value to validate the downloaded file.
            if None, skip hash validation.
        hash_type: 'md5' or 'sha1', defaults to 'md5'.

    """
    download_url(url=url, filepath=filepath, hash_val=hash_val, hash_type=hash_type)
    extractall(filepath=filepath, output_dir=output_dir, hash_val=hash_val, hash_type=hash_type)
