# SPDX-FileCopyrightText: 2020-2025 CERN.
# SPDX-FileCopyrightText: 2024 Graz University of Technology.
# SPDX-FileCopyrightText: 2025-2026 CESNET z.s.p.o.
# SPDX-FileCopyrightText: 2026 KTH Royal Institute of Technology.
# SPDX-License-Identifier: MIT

"""Configuration module.

Configuration values (e.g. service configuration) need to be set through
environment variables. However, sane defaults are provided below.

The list of services to be configured is taken from ``SERVICES``. Each one
should contain a ``<SERVICE_NAME>_VERSION`` variable.

Service's version are treated slightly different:

- If the variable is not found in the environment, it will use the set default.
- If the variable is set with a version number (e.g. 10, 10.7) it will use
  said value.
- If the variable is set with a string point to one of the configured
  ``latests`` it will load the value of said ``latest`` and use it.

This means that the environment set/load logic will first set the default
versions before loading a given service's version.
"""

DOCKER_SERVICES_FILEPATH = "docker-services.yml"
"""Docker services file default path."""

# Elasticsearch
ELASTICSEARCH = {
    "ELASTICSEARCH_VERSION": "ELASTICSEARCH_7_LATEST",
    "DEFAULT_VERSIONS": {
        "ELASTICSEARCH_7_LATEST": "7.10.2",  # the last of the OSS versions (https://github.com/elastic/elasticsearch/issues/58303)
    },
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "search": {
            "SEARCH_HOSTS": "\"[{'host': 'localhost', 'port': 9200}]\"",
        }
    },
}
"""Elasticsearch service configuration."""

# Opensearch
OPENSEARCH = {
    "OPENSEARCH_VERSION": "OPENSEARCH_2_LATEST",
    "DEFAULT_VERSIONS": {
        "OPENSEARCH_1_LATEST": "1.3.18",
        "OPENSEARCH_2_LATEST": "2.16.0",
    },
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "search": {
            "SEARCH_HOSTS": "\"[{'host': 'localhost', 'port': 9200}]\"",
        }
    },
}
"""Opensearch service configuration."""

# PostgreSQL
POSTGRESQL = {
    "POSTGRESQL_VERSION": "POSTGRESQL_16_LATEST",
    "DEFAULT_VERSIONS": {
        "POSTGRESQL_14_LATEST": "14.9",
        "POSTGRESQL_15_LATEST": "15.4",
        "POSTGRESQL_16_LATEST": "16.2",
    },
    "CONTAINER_CONFIG_ENVIRONMENT_VARIABLES": {
        "POSTGRESQL_USER": "invenio",
        "POSTGRESQL_PASSWORD": "invenio",
        "POSTGRESQL_DB": "invenio",
    },
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "db": {
            "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg2://invenio:invenio@localhost:5432/invenio"
        }
    },
}
"""Postgresql service configuration."""

# MySQL
MYSQL = {
    "MYSQL_VERSION": "MYSQL_8_LATEST",
    "DEFAULT_VERSIONS": {"MYSQL_8_LATEST": "8.3"},
    "CONTAINER_CONFIG_ENVIRONMENT_VARIABLES": {
        "MYSQL_USER": "invenio",
        "MYSQL_PASSWORD": "invenio",
        "MYSQL_DB": "invenio",
        "MYSQL_ROOT_PASSWORD": "invenio",
    },
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "db": {
            "SQLALCHEMY_DATABASE_URI": "mysql+pymysql://invenio:invenio@localhost:3306/invenio"
        }
    },
}
"""MySQL service configuration."""

REDIS = {
    "REDIS_VERSION": "REDIS_7_LATEST",
    "DEFAULT_VERSIONS": {
        "REDIS_6_LATEST": "6",
        "REDIS_7_LATEST": "7",
    },
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "mq": {"BROKER_URL": "redis://localhost:6379/0"},
        "cache": {"CACHE_TYPE": "RedisCache"},
    },
}
"""Redis service configuration."""

RABBITMQ = {
    "RABBITMQ_VERSION": "RABBITMQ_3_LATEST",
    "DEFAULT_VERSIONS": {"RABBITMQ_3_LATEST": "3"},
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "mq": {"BROKER_URL": "amqp://localhost:5672//"}
    },
}
"""RabbitMQ service configuration."""

RUSTFS = {
    "RUSTFS_VERSION": "RUSTFS_1_LATEST",
    # note: rustfs is still pre-1.0 (release candidates like 1.0.0-rc.6), so we
    # track the floating "latest" tag for the 1.x line rather than pinning a rc
    "DEFAULT_VERSIONS": {"RUSTFS_1_LATEST": "latest"},
    "CORS_ALLOWED_ORIGINS": (
        "http://localhost,http://127.0.0.1,"
        "https://localhost,https://127.0.0.1,"
        "http://localhost:5000,http://127.0.0.1:5000,"
        "https://localhost:5000,https://127.0.0.1:5000"
    ),
    "CONTAINER_CONFIG_ENVIRONMENT_VARIABLES": {
        "S3_ACCESS_KEY_ID": "invenio",
        # rustfs needs at least 8 characters for the secret
        "S3_SECRET_ACCESS_KEY": "invenio8",
    },
    "CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES": {
        "s3": {
            "S3_ENDPOINT_URL": "http://localhost:9000",
            "S3_ACCESS_KEY_ID": "invenio",
            # rustfs needs at least 8 characters for the secret
            "S3_SECRET_ACCESS_KEY": "invenio8",
        }
    },
}
"""RustFS service configuration."""

SERVICES = {
    "elasticsearch": ELASTICSEARCH,
    "opensearch": OPENSEARCH,
    "postgresql": POSTGRESQL,
    "mysql": MYSQL,
    "redis": REDIS,
    "rabbitmq": RABBITMQ,
    "rustfs": RUSTFS,
}
"""List of services to configure."""

SERVICES_ALL_DEFAULT_VERSIONS = {
    **ELASTICSEARCH.get("DEFAULT_VERSIONS", {}),
    **OPENSEARCH.get("DEFAULT_VERSIONS", {}),
    **POSTGRESQL.get("DEFAULT_VERSIONS", {}),
    **REDIS.get("DEFAULT_VERSIONS", {}),
    **MYSQL.get("DEFAULT_VERSIONS", {}),
    **RABBITMQ.get("DEFAULT_VERSIONS", {}),
    **RUSTFS.get("DEFAULT_VERSIONS", {}),
}
"""Services default latest versions."""

SERVICE_TYPES = {
    "search": ["opensearch", "elasticsearch"],
    "db": ["mysql", "postgresql"],
    "cache": [
        "redis",
    ],
    "mq": ["rabbitmq", "redis"],
    "s3": ["rustfs"],
}
"""Types of offered services."""
