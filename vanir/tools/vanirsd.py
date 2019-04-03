import asyncio
import os
import signal

import libvirtaio

import vanir
import vanir.api
import vanir.api.admin
import vanir.api.internal
import vanir.api.misc
import vanir.log
import vanir.utils
import vanir.vm.qubesvm

def sighandler(loop, signame, servers):
    print('caught {}, exiting'.format(signame))
    for server in servers:
        server.close()
    loop.stop()

parser = vanir.tools.VanirArgumentParser(description='vanir OS daemon')
parser.add_argument('--debug', action='store_true', default=False,
    help='Enable verbose error logging (all exceptions with full '
         'tracebacks) and also send tracebacks to Admin API clients')

def main(args=None):
    loop = asyncio.get_event_loop()
    libvirtaio.virEventRegisterAsyncIOImpl(loop=loop)
    try:
        args = parser.parse_args(args)
    except:
        loop.close()
        raise

    args.app.register_event_handlers()

    if args.debug:
        vanir.log.enable_debug()

    servers = loop.run_until_complete(vanir.api.create_servers(
        vanir.api.admin.QubesAdminAPI,
        vanir.api.internal.QubesInternalAPI,
        vanir.api.misc.QubesMiscAPI,
        app=args.app, debug=args.debug))

    socknames = []
    for server in servers:
        for sock in server.sockets:
            socknames.append(sock.getsockname())

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame),
            sighandler, loop, signame, servers)

    vanir.utils.systemd_notify()
    # make sure children will not inherit this
    os.environ.pop('NOTIFY_SOCKET', None)

    try:
        loop.run_forever()
        loop.run_until_complete(asyncio.wait([
            server.wait_closed() for server in servers]))
        for sockname in socknames:
            try:
                os.unlink(sockname)
            except FileNotFoundError:
                args.app.log.warning(
                    'socket {} got unlinked sometime before shutdown'.format(
                        sockname))
    finally:
        loop.close()

if __name__ == '__main__':
    main()