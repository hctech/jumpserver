from typing import Iterable
from uuid import UUID

from assets.models import SystemUser, Asset, Node
from assets.tasks import push_system_user_to_assets
from users.models import User, UserGroup
from common.decorator import on_transaction_commit


push_system_user_to_assets = on_transaction_commit(push_system_user_to_assets.delay)


def system_user_add_assets_with_push(system_user: SystemUser, assets_id: Iterable[UUID]):
    exists = system_user.assets.filter(id__in=assets_id).values_list('id', flat=True).distinct()
    system_user.assets.add(*assets_id)
    push_system_user_to_assets(system_user, exists)


def system_user_add_nodes_with_push(system_user: SystemUser, nodes_id: Iterable[UUID]):
    pass


def system_user_add_users_with_push(system_user: SystemUser, users_id: Iterable[UUID]):
    pass


def system_user_add_groups_with_push(system_user: SystemUser, groups_id: Iterable[UUID]):
    pass
