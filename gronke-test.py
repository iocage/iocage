import time
from iocage.lib.Jails import Jails
from iocage.lib.Jail import Jail
import sys

#uuid = "32101588-868f-4c1b-9e14-19a0ab7af04a"
#print(f"Starting Jail {uuid}")
#start_time = time.time()
#j = Jail({ "uuid": uuid })
#j.start()
#end_time = time.time()
#print(f"Jail started with JID {j.jid}")
#print("--- %s seconds ---" % (time.time() - start_time))
action = str(sys.argv[1])
counter = 0
start_time = time.time()
jail_list = Jails().list()
for jail in jail_list:
  print(f"UUID={jail.uuid} JID={jail.jid} TAG={jail.config.tag}")
  if jail.config.tag.startswith("test"):
    if action == "stop" and jail.running:
      jail.stop()
      counter+=1
      print(f"Stopped {jail.uuid} ({jail.config.tag}) #{jail.jid}")
    if action == "start" and not jail.running:
      jail.start()
      counter+=1
      print(f"Started {jail.uuid} ({jail.config.tag}) #{jail.jid}")
end_time = time.time()
print("--- %s seconds ---" % (time.time() - start_time))
print(f"Counter: {counter}")

