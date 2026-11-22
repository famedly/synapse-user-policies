ARG BASE
FROM ${BASE}
COPY pyproject.toml README.md /module/
COPY synapse_user_policies /module/synapse_user_policies
RUN pip install --no-deps /module
COPY complement/user_policies.yaml /conf/homeserver.d/user_policies.yaml
