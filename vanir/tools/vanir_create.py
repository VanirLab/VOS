import sys
import vanir
import vanir.tools

parser = vanir.tools.VanirArgumentParser(
    description='Create new Vanir OS store.',
    want_app=True,
    want_app_no_instance=True)

def main(args=None):
    '''Main routine of :program:`vanir-create`.
    :param list args: Optional arguments to override those delivered from \
        command line.
    '''

    args = parser.parse_args(args)
    vanir.vanir.create_empty_store(args.app,
        offline_mode=args.offline_mode).setup_pools()
    return 0


if __name__ == '__main__':
    sys.exit(main())
