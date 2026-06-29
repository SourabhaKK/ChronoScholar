from fastapi import Request


def get_cognee_service(request: Request):
    ...


def get_contradiction_service(request: Request):
    ...


def get_run_store(request: Request) -> dict:
    ...
