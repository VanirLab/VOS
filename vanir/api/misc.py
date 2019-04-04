import asyncio
import string

import vanir.api
import vanir.api.admin
import vanir.vm.dispvm


class QubesMiscAPI(vanir.api.AbstractVanirAPI):
    SOCKNAME = '/var/run/vanirsd.misc.sock'

    @vanir.api.method('vanir.FeaturesRequest', no_payload=True)
    @asyncio.coroutine
    def qubes_features_request(self):
        ''' vanir.FeaturesRequest handler
        VM (mostly templates) can request some features from dom0 for itself.
        Then dom0 (vanirsd extension) may respect this request or ignore it.
        Technically, VM first write requested features into QubesDB in
        `/features-request/` subtree, then call this method. The method will
        dispatch 'features-request' event, which may be handled by
        appropriate extensions. Requests not explicitly handled by some
        extension are ignored.
        '''
        self.enforce(self.dest.name == 'dom0')
        self.enforce(not self.arg)

        prefix = '/features-request/'

        keys = self.src.untrusted_qdb.list(prefix)
        untrusted_features = {key[len(prefix):]:
            self.src.untrusted_qdb.read(key).decode('ascii', errors='strict')
                for key in keys}

        safe_set = string.ascii_letters + string.digits
        for untrusted_key in untrusted_features:
            untrusted_value = untrusted_features[untrusted_key]
            self.enforce(all((c in safe_set) for c in untrusted_value))

        yield from self.src.fire_event_async('features-request',
            untrusted_features=untrusted_features)
        self.app.save()

    @vanir.api.method('vanir.NotifyTools', no_payload=True)
    @asyncio.coroutine
    def vanir_notify_tools(self):
        '''
        Legacy version of vanir.FeaturesRequest, used by Vanir Windows Tools
        '''
        self.enforce(self.dest.name == 'dom0')
        self.enforce(not self.arg)

        untrusted_features = {}
        safe_set = string.ascii_letters + string.digits
        expected_features = ('qrexec', 'gui', 'gui-emulated', 'default-user',
            'os')
        for feature in expected_features:
            untrusted_value = self.src.untrusted_qdb.read(
                '/vanir-tools/' + feature)
            if untrusted_value:
                untrusted_value = untrusted_value.decode('ascii',
                    errors='strict')
                self.enforce(all((c in safe_set) for c in untrusted_value))
                untrusted_features[feature] = untrusted_value
            del untrusted_value

        yield from self.src.fire_event_async('features-request',
            untrusted_features=untrusted_features)
        self.app.save()

    @vanir.api.method('vanir.NotifyUpdates')
    @asyncio.coroutine
    def vanir_notify_updates(self, untrusted_payload):
        '''
        Receive VM notification about updates availability
        Payload contains a single integer - either 0 (no updates) or some
        positive value (some updates).
        '''

        untrusted_update_count = untrusted_payload.strip()
        self.enforce(untrusted_update_count.isdigit())
        # now sanitized
        update_count = int(untrusted_update_count)
        del untrusted_update_count

        # look for the nearest updateable VM up in the template chain
        updateable_template = getattr(self.src, 'template', None)
        while updateable_template is not None and \
                not updateable_template.updateable:
            updateable_template = getattr(updateable_template, 'template', None)

        if self.src.updateable:
            # Just trust information from VM itself
            self.src.features['updates-available'] = bool(update_count)
            self.app.save()
        elif updateable_template is not None:
            # Hint about updates availability in template
            # If template is running - it will notify about updates itself
            if updateable_template.is_running():
                return
            # Ignore no-updates info
            if update_count > 0:
                # If VM is outdated, updates were probably already installed
                # in the template - ignore info
                if self.src.storage.outdated_volumes:
                    return
                updateable_template.features['updates-available'] = bool(
                    update_count)
                self.app.save()