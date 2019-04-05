import argparse
import logging
import logging.handlers
import os

import sys

import vanirpolicy

parser = argparse.ArgumentParser(description="Evaluate qrexec policy")

parser.add_argument("--assume-yes-for-ask", action="store_true",
    dest="assume_yes_for_ask", default=False,
    help="Allow run of service without confirmation if policy say 'ask'")
parser.add_argument("--just-evaluate", action="store_true",
    dest="just_evaluate", default=False,
    help="Do not run the service, only evaluate policy; "
         "retcode=0 means 'allow'")
parser.add_argument('domain_id', metavar='src-domain-id',
    help='Source domain ID (Xen ID or similar, not Vanir ID)')
parser.add_argument('domain', metavar='src-domain-name',
    help='Source domain name')
parser.add_argument('target', metavar='dst-domain-name',
    help='Target domain name')
parser.add_argument('service_name', metavar='service-name',
    help='Service name')
parser.add_argument('process_ident', metavar='process-ident',
    help='Qrexec process identifier - for connecting data channel')


def create_default_policy(service_name):
    policy_file = os.path.join(vanirpolicy.POLICY_DIR, service_name)
    with open(policy_file, "w") as policy:
        policy.write(
            "## Policy file automatically created on first service call.\n")
        policy.write(
            "## Feel free to edit.\n")
        policy.write("## Note that policy parsing stops at the first match\n")
        policy.write("\n")
        policy.write("## Please use a single # to start your custom comments\n")
        policy.write("\n")
        policy.write("@anyvm  @anyvm  ask\n")


def main(args=None):
    args = parser.parse_args(args)

    # Add source domain information, required by qrexec-client for establishing
    # connection
    caller_ident = args.process_ident + "," + args.domain + "," + args.domain_id
    log = logging.getLogger('vanirpolicy')
    log.setLevel(logging.INFO)
    if not log.handlers:
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        log.addHandler(handler)
    log_prefix = 'qrexec: {}: {} -> {}:'.format(
        args.service_name, args.domain, args.target)
    try:
        system_info = vanirpolicy.get_system_info()
    except vanirpolicy.VanirMgmtException as e:
        log.error('%s error getting system info: %s', log_prefix, str(e))
        return 1
    try:
        try:
            policy = vanirpolicy.Policy(args.service_name)
        except vanirpolicy.PolicyNotFound:
            service_name = args.service_name.split('+')[0]
            import pydbus
            bus = pydbus.SystemBus()
            proxy = bus.get('org.vos.PolicyAgent',
                '/org/vos/PolicyAgent')
            create_policy = proxy.ConfirmPolicyCreate(
                args.domain, service_name)
            if create_policy:
                create_default_policy(service_name)
                policy = vanirpolicy.Policy(args.service_name)
            else:
                raise

        action = policy.evaluate(system_info, args.domain, args.target)
        if args.assume_yes_for_ask and action.action == vanirpolicy.Action.ask:
            action.action = vanirpolicy.Action.allow
        if args.just_evaluate:
            return {
                vanirpolicy.Action.allow: 0,
                vanirpolicy.Action.deny: 1,
                vanirpolicy.Action.ask: 1,
            }[action.action]
        if action.action == vanirpolicy.Action.ask:
            # late import to save on time for allow/deny actions
            import pydbus
            bus = pydbus.SystemBus()
            proxy = bus.get('org.vos.PolicyAgent',
                '/org/vos/PolicyAgent')

            icons = {name: system_info['domains'][name]['icon']
                for name in system_info['domains'].keys()}
            for dispvm_base in system_info['domains']:
                if not (system_info['domains'][dispvm_base]
                        ['template_for_dispvms']):
                    continue
                dispvm_api_name = '@dispvm:' + dispvm_base
                icons[dispvm_api_name] = \
                    system_info['domains'][dispvm_base]['icon']
                icons[dispvm_api_name] = \
                    icons[dispvm_api_name].replace('app', 'disp')

            response = proxy.Ask(args.domain, args.service_name,
                action.targets_for_ask, action.target or '', icons)
            if response:
                action.handle_user_response(True, response)
            else:
                action.handle_user_response(False)
        log.info('%s allowed to %s', log_prefix, str(action.target))
        action.execute(caller_ident)
    except vanirpolicy.PolicySyntaxError as e:
        log.error('%s error loading policy: %s', log_prefix, str(e))
        return 1
    except vanirpolicy.AccessDenied as e:
        log.info('%s denied: %s', log_prefix, str(e))
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())