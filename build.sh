set -e
set -o pipefail 

VANIR_DIST="vanir-rolling"
VANIR_VERSION=""
VANIR_VARIANT="default"
TARGET_DIR="$(dirname $0)/images"
TARGET_SUBDIR=""
SUDO="sudo"
VERBOSE=""
HOST_ARCH=$(dpkg --print-architecture)

image_name() {
	local arch=$1

	case "$arch" in
		i386|amd64)
			IMAGE_TEMPLATE="live-image-ARCH.hybrid.iso"
		;;
		armel|armhf)
			IMAGE_TEMPLATE="live-image-ARCH.img"
		;;
	esac
	echo $IMAGE_TEMPLATE | sed -e "s/ARCH/$arch/"
}

target_image_name() {
	local arch=$1

	IMAGE_NAME="$(image_name $arch)"
	IMAGE_EXT="${IMAGE_NAME##*.}"
	if [ "$IMAGE_EXT" = "$IMAGE_NAME" ]; then
		IMAGE_EXT="img"
	fi
	if [ "$VANIR_VARIANT" = "default" ]; then
		echo "${TARGET_SUBDIR:+$TARGET_SUBDIR/}vanir-linux-$VANIR_VERSION-$VANIR_ARCH.$IMAGE_EXT"
	else
		echo "${TARGET_SUBDIR:+$TARGET_SUBDIR/}vanir-linux-$VANIR_VARIANT-$VANIR_VERSION-$VANIR_ARCH.$IMAGE_EXT"
	fi
}

target_build_log() {
	TARGET_IMAGE_NAME=$(target_image_name $1)
	echo ${TARGET_IMAGE_NAME%.*}.log
}

default_version() {
	case "$1" in
	    vanir-*)
		echo "${1#vanir-}"
		;;
	    *)
		echo "$1"
		;;
	esac
}

failure() {
	# Cleanup update-vanir-menu that might stay around so that the
	# build chroot can be properly unmounted
	$SUDO pkill -f update-vanir-menu || true
	echo "Build of $VANIR_DIST/$VANIR_VARIANT/$VANIR_ARCH live image failed (see build.log for details)" >&2
	exit 2
}

run_and_log() {
	if [ -n "$VERBOSE" ]; then
		"$@" 2>&1 | tee -a build.log
	else
		"$@" >>build.log 2>&1
	fi
	return $?
}

. $(dirname $0)/.getopt.sh

# Parsing command line options
temp=$(getopt -o "$BUILD_OPTS_SHORT" -l "$BUILD_OPTS_LONG,get-image-path" -- "$@")
eval set -- "$temp"
while true; do
	case "$1" in
		-d|--distribution) VANIR_DIST="$2"; shift 2; ;;
		-p|--proposed-updates) OPT_pu="1"; shift 1; ;;
		-a|--arch) VANIR_ARCHES="${VANIR_ARCHES:+$VANIR_ARCHES } $2"; shift 2; ;;
		-v|--verbose) VERBOSE="1"; shift 1; ;;
		-s|--salt) shift; ;;
		--variant) VANIR_VARIANT="$2"; shift 2; ;;
		--version) VANIR_VERSION="$2"; shift 2; ;;
		--subdir) TARGET_SUBDIR="$2"; shift 2; ;;
		--get-image-path) ACTION="get-image-path"; shift 1; ;;
		--) shift; break; ;;
		*) echo "ERROR: Invalid command-line option: $1" >&2; exit 1; ;;
        esac
done

# Set default values
VANIR_ARCHES=${VANIR_ARCHES:-$HOST_ARCH}
if [ -z "$VANIR_VERSION" ]; then
	VANIR_VERSION="$(default_version $VANIR_DIST)"
fi

# Check parameters
for arch in $VANIR_ARCHES; do
	if [ "$arch" = "$HOST_ARCH" ]; then
		continue
	fi
	case "$HOST_ARCH/$arch" in
		amd64/i386|i386/amd64)
		;;
		*)
			echo "Can't build $arch image on $HOST_ARCH system." >&2
			exit 1
		;;
	esac
done
if [ ! -d "$(dirname $0)/vanir-config/variant-$VANIR_VARIANT" ]; then
	echo "ERROR: Unknown variant of Vanir configuration: $VANIR_VARIANT" >&2
fi

# Build parameters for lb config
VANIR_CONFIG_OPTS="--distribution $VANIR_DIST -- --variant $VANIR_VARIANT"
if [ -n "$OPT_pu" ]; then
	VANIR_CONFIG_OPTS="$VANIR_CONFIG_OPTS --proposed-updates"
	VANIR_DIST="$VANIR_DIST+pu"
fi

# helper for apt-cacher-ng
if [ -n "$http_proxy" ]; then
  VANIR_CONFIG_OPTS="$VANIR_CONFIG_OPTS --apt-http-proxy $http_proxy"
fi

# Set sane PATH (cron seems to lack /sbin/ dirs)
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Either we use a git checkout of live-build
# export LIVE_BUILD=/srv/cdimage.vanir.org/live/live-build

# Or we ensure we have proper version installed
ver_live_build=$(dpkg-query -f '${Version}' -W live-build)
if dpkg --compare-versions "$ver_live_build" lt 1:20151215kali1; then
	echo "ERROR: You need live-build (>= 1:20151215kali1), you have $ver_live_build" >&2
	exit 1
fi

# Check we have a good debootstrap
ver_debootstrap=$(dpkg-query -f '${Version}' -W debootstrap)
if dpkg --compare-versions "$ver_debootstrap" lt "1.0.97"; then
	if ! echo "$ver_debootstrap" | grep -q vanir; then
		echo "ERROR: You need debootstrap >= 1.0.97 (or a Vanir patched debootstrap). Your current version: $ver_debootstrap" >&2
		exit 1
	fi
fi

# We need root rights at some point
if [ "$(whoami)" != "root" ]; then
	if ! which $SUDO >/dev/null; then
		echo "ERROR: $0 is not run as root and $SUDO is not available" >&2
		exit 1
	fi
else
	SUDO="" # We're already root
fi

if [ "$ACTION" = "get-image-path" ]; then
	for VANIR_ARCH in $VANIR_ARCHES; do
		echo $(target_image_name $VANIR_ARCH)
	done
	exit 0
fi

cd $(dirname $0)
mkdir -p $TARGET_DIR/$TARGET_SUBDIR

for VANIR_ARCH in $VANIR_ARCHES; do
	IMAGE_NAME="$(image_name $VANIR_ARCH)"
	set +e
	: > build.log
	run_and_log $SUDO lb clean --purge
	[ $? -eq 0 ] || failure
	run_and_log lb config -a $VANIR_ARCH $VANIR_CONFIG_OPTS "$@"
	[ $? -eq 0 ] || failure
	run_and_log $SUDO lb build
	if [ $? -ne 0 ] || [ ! -e $IMAGE_NAME ]; then
		failure
	fi
	set -e
	mv -f $IMAGE_NAME $TARGET_DIR/$(target_image_name $VANIR_ARCH)
	mv -f build.log $TARGET_DIR/$(target_build_log $VANIR_ARCH)
done