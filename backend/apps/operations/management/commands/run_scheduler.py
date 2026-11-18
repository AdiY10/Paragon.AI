import json
import signal
import threading
import uuid
from django.core.management.base import BaseCommand,CommandError
from apps.operations.scheduler import dispatch_due,release_leader

class Command(BaseCommand):
    help='Dispatch Eastern wall-clock schedules under a renewable database lease.'
    def add_arguments(self,parser):
        parser.add_argument('--once',action='store_true')
        parser.add_argument('--interval',type=int,default=5)
    def handle(self,*args,**options):
        if not 1<=options['interval']<=30:
            raise CommandError('Scheduler interval must be between 1 and 30 seconds.')
        owner=uuid.uuid4()
        stop=threading.Event()
        previous={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
        for sig in previous:
            signal.signal(sig,lambda *_:stop.set())
        try:
            while not stop.is_set():
                self.stdout.write(json.dumps(dispatch_due(owner=owner)))
                if options['once']:break
                stop.wait(options['interval'])
        except KeyboardInterrupt:
            pass
        finally:
            release_leader(owner)
            for sig,handler in previous.items():
                signal.signal(sig,handler)
