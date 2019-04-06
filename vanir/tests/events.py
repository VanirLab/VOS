import asyncio

import vanir.events
import vanir.tests

class TC_00_Emitter(vanir.tests.VanirTestCase):
    def test_000_add_handler(self):
        # need something mutable
        testevent_fired = [False]

        def on_testevent(subject, event):
            # pylint: disable=unused-argument
            if event == 'testevent':
                testevent_fired[0] = True

        emitter = vanir.events.Emitter()
        emitter.add_handler('testevent', on_testevent)
        emitter.events_enabled = True
        emitter.fire_event('testevent')
        self.assertTrue(testevent_fired[0])


    def test_001_decorator(self):
        class TestEmitter(vanir.events.Emitter):
            def __init__(self):
                # pylint: disable=bad-super-call
                super(TestEmitter, self).__init__()
                self.testevent_fired = False

            @vanir.events.handler('testevent')
            def on_testevent(self, event):
                if event == 'testevent':
                    self.testevent_fired = True

        emitter = TestEmitter()
        emitter.events_enabled = True
        emitter.fire_event('testevent')
        self.assertTrue(emitter.testevent_fired)

    def test_002_fire_for_effect(self):
        class TestEmitter(vanir.events.Emitter):
            @vanir.events.handler('testevent')
            def on_testevent_1(self, event):
                pass

            @vanir.events.handler('testevent')
            def on_testevent_2(self, event):
                yield 'testvalue1'
                yield 'testvalue2'

            @vanir.events.handler('testevent')
            def on_testevent_3(self, event):
                return ('testvalue3', 'testvalue4')

        emitter = TestEmitter()
        emitter.events_enabled = True

        effect = emitter.fire_event('testevent')

        self.assertCountEqual(effect,
            ('testvalue1', 'testvalue2', 'testvalue3', 'testvalue4'))

    def test_004_catch_all(self):
        # need something mutable
        testevent_fired = [0]

        def on_all(subject, event, *args, **kwargs):
            # pylint: disable=unused-argument
            testevent_fired[0] += 1

        def on_foo(subject, event, *args, **kwargs):
            # pylint: disable=unused-argument
            testevent_fired[0] += 1

        emitter = vanir.events.Emitter()
        emitter.add_handler('*', on_all)
        emitter.add_handler('foo', on_foo)
        emitter.events_enabled = True
        emitter.fire_event('testevent')
        self.assertEqual(testevent_fired[0], 1)
        emitter.fire_event('foo')
        # now catch-all and foo should be executed
        self.assertEqual(testevent_fired[0], 3)
        emitter.fire_event('bar')
        self.assertEqual(testevent_fired[0], 4)

    def test_005_instance_handlers(self):
        class TestEmitter(vanir.events.Emitter):
            @vanir.events.handler('testevent')
            def on_testevent_1(self, event):
                yield 'testevent_1'

        def on_testevent_2(subject, event):
            yield 'testevent_2'

        emitter = TestEmitter()
        emitter.add_handler('testevent', on_testevent_2)
        emitter.events_enabled = True

        emitter2 = TestEmitter()
        emitter2.events_enabled = True

        with self.subTest('fire_event'):
            effect = emitter.fire_event('testevent')
            effect2 = emitter2.fire_event('testevent')
            self.assertEqual(list(effect),
                ['testevent_1', 'testevent_2'])
            self.assertEqual(list(effect2),
                ['testevent_1'])

        with self.subTest('fire_event_pre'):
            effect = emitter.fire_event('testevent', pre_event=True)
            effect2 = emitter2.fire_event('testevent', pre_event=True)
            self.assertEqual(list(effect),
                ['testevent_2', 'testevent_1'])
            self.assertEqual(list(effect2),
                ['testevent_1'])

    def test_005_fire_for_effect_async(self):
        class TestEmitter(vanir.events.Emitter):
            @vanir.events.handler('testevent')
            @asyncio.coroutine
            def on_testevent_1(self, event):
                pass

            @vanir.events.handler('testevent')
            @asyncio.coroutine
            def on_testevent_2(self, event):
                yield from asyncio.sleep(0.01)
                return ['testvalue1']

            @vanir.events.handler('testevent')
            @asyncio.coroutine
            def on_testevent_3(self, event):
                return ('testvalue2', 'testvalue3')

            @vanir.events.handler('testevent')
            def on_testevent_4(self, event):
                return ('testvalue4',)

        loop = asyncio.get_event_loop()
        emitter = TestEmitter()
        emitter.events_enabled = True

        effect = loop.run_until_complete(emitter.fire_event_async('testevent'))

        self.assertCountEqual(effect,
            ('testvalue1', 'testvalue2', 'testvalue3', 'testvalue4'))

    def test_006_wildcard(self):
        # need something mutable
        testevent_fired = [0]

        def on_foobar(subject, event, *args, **kwargs):
            # pylint: disable=unused-argument
            testevent_fired[0] += 1

        def on_foo(subject, event, *args, **kwargs):
            # pylint: disable=unused-argument
            testevent_fired[0] += 1

        emitter = vanir.events.Emitter()
        emitter.add_handler('foo:*', on_foo)
        emitter.add_handler('foo:bar', on_foobar)
        emitter.events_enabled = True
        emitter.fire_event('foo:testevent')
        self.assertEqual(testevent_fired[0], 1)
        emitter.fire_event('foo:bar')
        # now foo:bar and foo:* should be executed
        self.assertEqual(testevent_fired[0], 3)
        emitter.fire_event('foo:')
        self.assertEqual(testevent_fired[0], 4)
        emitter.fire_event('testevent')
        self.assertEqual(testevent_fired[0], 4)
