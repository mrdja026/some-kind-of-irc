#!/usr/bin/env bash
set -euo pipefail

TLS_CERT_PATH="${TLS_CERT_PATH:-}"
TLS_KEY_PATH="${TLS_KEY_PATH:-}"
TLS_SECRET_NAME="${TLS_SECRET_NAME:-ingress-nginx-tls}"
TLS_NAMESPACE="${TLS_NAMESPACE:-ingress-nginx}"
INGRESS_DEPLOYMENT="${INGRESS_DEPLOYMENT:-ingress-nginx-controller}"
NGINX_SERVICE_NAME="${NGINX_SERVICE_NAME:-nginx}"

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: required command not found: $cmd" >&2
        exit 1
    fi
}

usage() {
    cat <<'EOF'
Usage:
  TLS_CERT_PATH=/path/to/cert.pem \
  TLS_KEY_PATH=/path/to/key.pem \
  ./scripts/vps-ingress-hostports-tls.sh

Optional env:
  TLS_SECRET_NAME=ingress-nginx-tls
  TLS_NAMESPACE=ingress-nginx
  INGRESS_DEPLOYMENT=ingress-nginx-controller
  NGINX_SERVICE_NAME=nginx
EOF
}

stop_system_nginx() {
    if systemctl list-unit-files | grep -q "^${NGINX_SERVICE_NAME}\.service"; then
        if systemctl is-active --quiet "$NGINX_SERVICE_NAME"; then
            echo "Stopping ${NGINX_SERVICE_NAME}..."
            sudo systemctl stop "$NGINX_SERVICE_NAME"
        fi
        if systemctl is-enabled --quiet "$NGINX_SERVICE_NAME"; then
            echo "Disabling ${NGINX_SERVICE_NAME}..."
            sudo systemctl disable "$NGINX_SERVICE_NAME"
        fi
        echo "Masking ${NGINX_SERVICE_NAME} to prevent auto-start..."
        sudo systemctl mask "$NGINX_SERVICE_NAME" >/dev/null 2>&1 || true
    else
        echo "${NGINX_SERVICE_NAME} service not found; skipping stop/disable."
    fi
}

ensure_ports_free() {
    if sudo ss -lntp | egrep -q ':80|:443'; then
        echo "Error: ports 80/443 are still in use." >&2
        sudo ss -lntp | egrep ':80|:443' || true
        exit 1
    fi
}

create_tls_secret() {
    if [[ -z "$TLS_CERT_PATH" || -z "$TLS_KEY_PATH" ]]; then
        usage
        echo "Error: TLS_CERT_PATH and TLS_KEY_PATH are required." >&2
        exit 1
    fi

    if [[ ! -f "$TLS_CERT_PATH" ]]; then
        echo "Error: cert not found: $TLS_CERT_PATH" >&2
        exit 1
    fi
    if [[ ! -f "$TLS_KEY_PATH" ]]; then
        echo "Error: key not found: $TLS_KEY_PATH" >&2
        exit 1
    fi

    echo "Creating/updating TLS secret ${TLS_NAMESPACE}/${TLS_SECRET_NAME}..."
    kubectl -n "$TLS_NAMESPACE" create secret tls "$TLS_SECRET_NAME" \
        --cert="$TLS_CERT_PATH" \
        --key="$TLS_KEY_PATH" \
        --dry-run=client -o yaml | kubectl apply -f -
}

ensure_default_tls_arg() {
    local default_arg="--default-ssl-certificate=${TLS_NAMESPACE}/${TLS_SECRET_NAME}"
    local args

    args=$(kubectl -n "$TLS_NAMESPACE" get deployment "$INGRESS_DEPLOYMENT" \
        -o jsonpath='{.spec.template.spec.containers[0].args[*]}' 2>/dev/null || true)

    if [[ -z "$args" ]]; then
        echo "Error: could not read ingress controller args. Is ${INGRESS_DEPLOYMENT} running?" >&2
        exit 1
    fi

    if [[ "$args" != *"$default_arg"* ]]; then
        echo "Patching ingress controller with default TLS cert..."
        local patch_payload
        patch_payload=$(cat <<EOF
[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"${default_arg}"}]
EOF
)
        kubectl -n "$TLS_NAMESPACE" patch deployment "$INGRESS_DEPLOYMENT" --type='json' -p "$patch_payload"
    else
        echo "Default TLS cert arg already set."
    fi
}

restart_ingress() {
    echo "Restarting ingress controller..."
    kubectl -n "$TLS_NAMESPACE" rollout restart deployment "$INGRESS_DEPLOYMENT"
    kubectl -n "$TLS_NAMESPACE" wait --for=condition=available --timeout=300s deployment "$INGRESS_DEPLOYMENT"
}

main() {
    require_cmd kubectl
    require_cmd systemctl
    require_cmd ss

    stop_system_nginx
    ensure_ports_free

    create_tls_secret
    ensure_default_tls_arg
    restart_ingress

    echo "Done. Test with:"
    echo "  curl -k https://<VPS_IP>/health"
}

main "$@"
