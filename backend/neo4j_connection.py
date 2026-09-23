import os
from dataclasses import dataclass

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError


load_dotenv()


@dataclass(frozen=True)
class Neo4jTarget:
    name: str
    uri: str
    username: str
    password: str
    database: str


def _candidate_targets() -> list[Neo4jTarget]:
    cloud_uri = os.getenv("NEO4J_CLOUD_URI", "").strip()
    cloud_user = os.getenv("NEO4J_CLOUD_USERNAME", "").strip()
    cloud_password = os.getenv("NEO4J_CLOUD_PASSWORD", "").strip()
    cloud_database = os.getenv("NEO4J_CLOUD_DATABASE", "neo4j").strip() or "neo4j"

    local_uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687").strip()
    local_user = os.getenv("NEO4J_USERNAME", "neo4j").strip()
    local_password = os.getenv("NEO4J_PASSWORD", "").strip()
    local_database = os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    local_target: Neo4jTarget | None = None
    docker_local_target: Neo4jTarget | None = None
    cloud_target: Neo4jTarget | None = None

    if local_uri and local_user:
        local_target = Neo4jTarget(
            name="local",
            uri=local_uri,
            username=local_user,
            password=local_password,
            database=local_database,
        )
        if "localhost" in local_uri:
            docker_local_target = Neo4jTarget(
                name="docker_local",
                uri=local_uri.replace("localhost", "neo4j"),
                username=local_user,
                password=local_password,
                database=local_database,
            )

    if cloud_uri and cloud_user and cloud_password:
        cloud_target = Neo4jTarget(
            name="cloud",
            uri=cloud_uri,
            username=cloud_user,
            password=cloud_password,
            database=cloud_database,
        )

    # Optional explicit override:
    #   NEO4J_TARGET=local -> prefer local first
    #   NEO4J_TARGET=cloud -> prefer cloud first
    # default: cloud-first with local fallback.
    preferred = os.getenv("NEO4J_TARGET", "cloud").strip().lower()
    if preferred == "cloud":
        ordered = [cloud_target, local_target, docker_local_target]
    else:
        ordered = [local_target, docker_local_target, cloud_target]

    return [target for target in ordered if target is not None]


def get_neo4j_driver_with_fallback() -> tuple[object, Neo4jTarget]:
    errors: list[str] = []

    for target in _candidate_targets():
        if not target.password:
            errors.append(f"{target.name}: missing password")
            continue

        try:
            driver = GraphDatabase.driver(
                target.uri,
                auth=(target.username, target.password),
            )
            driver.verify_connectivity()
            return driver, target
        except (OSError, Neo4jError, Exception) as exc:
            errors.append(f"{target.name}: {exc}")

    details = "; ".join(errors) if errors else "no Neo4j targets configured"
    raise RuntimeError(f"Unable to connect to Neo4j. {details}")