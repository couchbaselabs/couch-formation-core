##
##

import attr


@attr.s
class ContainerBuildMap(object):
    build_map = {
        'cbs': 'couchbase/server',
        'sgw': 'couchbase/sync-gateway'
    }

    def image(self, build):
        return self.build_map.get(build)
