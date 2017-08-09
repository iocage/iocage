def _delete_dataset_recursive(dataset):
    for child in dataset.children:
        _delete_dataset_recursive(child)
    dataset.delete()

def unmount_and_destroy_dataset_recursive(dataset):
    dataset.umount_recursive()
    _delete_dataset_recursive(dataset)
