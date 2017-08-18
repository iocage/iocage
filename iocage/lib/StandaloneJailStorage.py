class StandaloneJailStorage:

    def apply(self, release):
        self.logger.warn(
            "Standalone jails do not require storage operations to start",
            jail=self.jail
        )

    def setup(self, release):
        try:
            self.jail_root_dataset
            self.logger.warn(
                f"The dataset '{self.jail_root_dataset_name}' already exists"
                "- skipping setup",
                jail=self.jail
            )
            return
        except:
            pass

        self.logger.verbose("Cloning the release once to the root dataset")
        self.clone_release(release)
