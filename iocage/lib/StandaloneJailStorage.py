import time

class StandaloneJailStorage:

  def apply(self, release):
    self.logger.warn("Standalone jails do not require storage operations to start.", jail=self.jail)

  def setup(self, release):
    try:
      self.jail_root_dataset
      self.logger.warn(f"The dataset '{self.jail_root_dataset_name}' already exists. Skipping setup.", jail=self.jail)
      return
    except:
      pass

    # Clone the release once to the root dataset
    start_time = time.time()
    self.clone_release(release)
    end_time = time.time()
    print("--- %s seconds ---" % (time.time() - start_time))
