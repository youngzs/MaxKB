#!/usr/bin/env bash
#
# MaxKB 测试环境发布脚本
# ============================================================================
# 把指定的改动文件发布到测试环境容器，并固化为新镜像。
# 把「scp → docker cp → 校验 → restart → 健康检查 → docker commit」这套
# 手动部署动作固化为一条可重复执行的发布流程。
#
# 用法:
#   installer/deploy-test.sh <file> [file ...]
#
#   <file>  相对仓库根的路径，容器内目标自动为 $APP_ROOT/<同路径>。例:
#     installer/deploy-test.sh \
#       apps/application/chat_pipeline/step/search_dataset_step/mmr.py \
#       apps/application/chat_pipeline/step/search_dataset_step/query_split.py
#
# 环境变量(均有默认值，按需覆盖):
#   DEPLOY_HOST       测试服务器        默认 1.13.169.98
#   DEPLOY_USER       SSH 用户          默认 root
#   DEPLOY_KEY        SSH 私钥路径      默认 ~/.ssh/yangyubo.pem
#   DEPLOY_CONTAINER  容器名            默认 1Panel-maxkb-5IZn
#   APP_ROOT          容器内代码根      默认 /opt/maxkb-app
#   DEPLOY_TAG_SUFFIX docker commit tag 后缀，例: -retrieval-abc
#   SKIP_COMMIT       =1 时跳过 docker commit 固化
#
# 流程: tar 传输 → docker cp(先备份) → py_compile 校验 → [collect_static] →
#       restart → 健康检查 → docker commit + tag latest
# py_compile 失败会用备份自动回滚且不重启 —— 旧代码继续服务，发布安全中止。
#
# 注意: 本脚本只把代码 cp 进运行中的容器并固化镜像。要让容器正式基于新镜像
#       运行，需到 1panel 控制台把镜像版本切到 maxkb-custom:latest 并重启
#       (CLI 切换容易漏 1panel 隐式管理的 mount/network)。
# ============================================================================
set -euo pipefail

HOST="${DEPLOY_HOST:-1.13.169.98}"
USER="${DEPLOY_USER:-root}"
KEY="${DEPLOY_KEY:-$HOME/.ssh/yangyubo.pem}"
CONTAINER="${DEPLOY_CONTAINER:-1Panel-maxkb-5IZn}"
APP_ROOT="${APP_ROOT:-/opt/maxkb-app}"
TAG_SUFFIX="${DEPLOY_TAG_SUFFIX:-}"
SKIP_COMMIT="${SKIP_COMMIT:-0}"

[ $# -ge 1 ] || { echo "用法: $0 <file> [file ...]  (路径相对仓库根)" >&2; exit 1; }

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# --- 校验本地文件、归类 -------------------------------------------------------
FILES=("$@")
NEED_STATIC=0
PYFILES=()
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "ERROR: 本地文件不存在: $f" >&2; exit 1; }
  [[ "$f" == ui/* ]] && NEED_STATIC=1
  [[ "$f" == *.py ]] && PYFILES+=("$APP_ROOT/$f")
done
FILES_STR="${FILES[*]}"
PYFILES_STR="${PYFILES[*]:-}"

SHA="$(git rev-parse --short HEAD)"
IMAGE_TAG="maxkb-custom:${SHA}${TAG_SUFFIX}"
SSH="ssh -i $KEY -o LogLevel=ERROR -o StrictHostKeyChecking=accept-new $USER@$HOST"
TS="$(date +%Y%m%d-%H%M%S)"
STAGE="/tmp/maxkb-deploy-$TS"
BACKUP="/tmp/maxkb-deploy-backup-$TS"

echo "==> 发布 ${#FILES[@]} 个文件到 $CONTAINER @ $HOST"
printf '      %s\n' "${FILES[@]}"

# --- [1/6] tar 打包传输(保留目录结构) ----------------------------------------
echo "==> [1/6] 传输文件到服务器 $STAGE"
tar czf - "${FILES[@]}" | $SSH "mkdir -p '$STAGE' && tar xzf - -C '$STAGE'"

# --- [2/6]~[6/6] 远程主流程(单次 ssh) ----------------------------------------
$SSH bash -s <<REMOTE
set -e

echo "==> [2/6] 备份容器内原文件并拷入新文件"
for f in $FILES_STR; do
  mkdir -p "$BACKUP/\$(dirname "\$f")"
  if docker exec $CONTAINER test -e "$APP_ROOT/\$f"; then
    docker cp "$CONTAINER:$APP_ROOT/\$f" "$BACKUP/\$f"
  fi
  docker exec $CONTAINER mkdir -p "$APP_ROOT/\$(dirname "\$f")"
  docker cp "$STAGE/\$f" "$CONTAINER:$APP_ROOT/\$f"
done
echo "      备份位于 $BACKUP (回退用)"

echo "==> [3/6] py_compile 校验"
if [ -n "$PYFILES_STR" ]; then
  if ! docker exec $CONTAINER python -m py_compile $PYFILES_STR; then
    echo "ERROR: py_compile 失败 —— 回滚并中止(不重启，旧代码继续服务)" >&2
    for f in $FILES_STR; do
      if [ -e "$BACKUP/\$f" ]; then
        docker cp "$BACKUP/\$f" "$CONTAINER:$APP_ROOT/\$f"
      else
        docker exec $CONTAINER rm -f "$APP_ROOT/\$f"
      fi
    done
    echo "      已回滚到发布前状态" >&2
    exit 1
  fi
  echo "      通过"
else
  echo "      无 .py 文件，跳过"
fi

echo "==> [4/6] collect_static"
if [ "$NEED_STATIC" = "1" ]; then
  docker exec $CONTAINER python $APP_ROOT/main.py collect_static
  echo "      前端静态文件已收集"
else
  echo "      无 ui/ 改动，跳过"
fi

echo "==> [5/6] 重启容器并等待服务就绪"
docker restart $CONTAINER >/dev/null
ready=0
for i in \$(seq 1 45); do
  code=\$(docker exec $CONTAINER curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ 2>/dev/null || true)
  if [ "\$code" = "200" ] || [ "\$code" = "302" ]; then
    echo "      服务就绪 (探测 \$i 次, HTTP \$code)"; ready=1; break
  fi
  sleep 5
done
if [ "\$ready" != "1" ]; then
  echo "ERROR: 服务在 225s 内未就绪 —— 检查 docker logs $CONTAINER" >&2
  exit 1
fi

echo "==> [6/6] 固化镜像"
if [ "$SKIP_COMMIT" = "1" ]; then
  echo "      SKIP_COMMIT=1，跳过 docker commit"
else
  docker commit --message "deploy @$SHA via deploy-test.sh" $CONTAINER "$IMAGE_TAG"
  docker tag "$IMAGE_TAG" maxkb-custom:latest
  echo "      已固化: $IMAGE_TAG (+ latest)"
fi
REMOTE

echo ""
echo "✅ 发布完成。"
[ "$SKIP_COMMIT" = "1" ] || echo "   新镜像: $IMAGE_TAG (latest 已指向它)"
echo "   回退备份: 服务器 $BACKUP"
echo "   让容器正式基于新镜像运行 → 到 1panel 把镜像版本切到 maxkb-custom:latest。"
