"""sandbox attestation -- signs task results with the node's mTLS key."""

import hashlib
import json
import os
import time


def build_attestation(task_id, sandbox_config, input_hash, output, node_key_path=None):
    """build a signed attestation blob for a completed task.

    the attestation includes:
    - task_id
    - sha256 of sandbox config (runtime, limits)
    - sha256 of input (prompt + workspace)
    - sha256 of output
    - wall clock timestamp
    - node signature (if key available)
    """
    payload = {
        "task_id": task_id,
        "sandbox_hash": _hash_dict(sandbox_config),
        "input_hash": input_hash,
        "output_hash": hashlib.sha256(output.encode()).hexdigest(),
        "timestamp": int(time.time()),
        "version": "0.1",
    }

    payload_bytes = json.dumps(payload, sort_keys=True).encode()

    # sign with node mTLS key if available
    signature = None
    if node_key_path and os.path.exists(node_key_path):
        signature = _sign_payload(payload_bytes, node_key_path)

    return {
        "payload": payload,
        "signature": signature,
        "raw": payload_bytes,
    }


def verify_attestation(attestation, node_cert_path):
    """verify an attestation blob against a node's certificate."""
    if not attestation.get("signature"):
        return False

    payload_bytes = json.dumps(
        attestation["payload"], sort_keys=True
    ).encode()

    return _verify_signature(payload_bytes, attestation["signature"], node_cert_path)


def _hash_dict(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def _sign_payload(data, key_path):
    """sign payload bytes with PEM private key."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        with open(key_path, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)

        return key.sign(data, padding.PKCS1v15(), hashes.SHA256()).hex()
    except ImportError:
        return None


def _verify_signature(data, signature, cert_path):
    """verify signature against a PEM certificate's public key."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.x509 import load_pem_x509_certificate

        with open(cert_path, "rb") as f:
            cert = load_pem_x509_certificate(f.read())

        pubkey = cert.public_key()
        pubkey.verify(bytes.fromhex(signature), data, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False
