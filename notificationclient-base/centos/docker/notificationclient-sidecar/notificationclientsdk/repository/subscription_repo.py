import time, uuid
import logging

from sqlalchemy.orm         import scoped_session, sessionmaker

from notificationclientsdk.model.orm.subscription import Subscription as SubscriptionOrm
from notificationclientsdk.repository.dbcontext import DbContext

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

class SubscriptionRepo(DbContext):

    def __init__(self, session=None, autocommit=False):
        self.autocommit = autocommit
        super(SubscriptionRepo, self).__init__(session)
        if session:
            self.own_session = False
        else:
            self.own_session = True

    def __del__(self):
        if self.own_session:
            self.clear()

    def add(self, subscription):
        try:
            subscription.SubscriptionId = str(uuid.uuid1())
            subscription.Status = 1
            subscription.CreateTime = time.time()
            subscription.LastUpdateTime = subscription.CreateTime
            subscription.UriLocation = "{0}/{1}".format(
                subscription.UriLocation, subscription.SubscriptionId)

            self.session.add(subscription)
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()
            return subscription

    def update(self, subscriptionid, **data):
        try:
            data['LastUpdateTime'] = time.time()
            self.session.query(SubscriptionOrm).filter_by(SubscriptionId=subscriptionid).update(data)
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()

    def get_one(self, **filter):
        return self.session.query(SubscriptionOrm).filter_by(**filter).first()

    def get(self, **filter):
        return self.session.query(SubscriptionOrm).filter_by(**filter)

    def delete_one(self, **filter):
        try:
            entry = self.session.query(SubscriptionOrm).filter_by(**filter).first()
            self.session.delete(entry)
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()

    def delete(self, **filter):
        try:
            entry = self.session.query(SubscriptionOrm).filter_by(**filter).delete()
        except Exception as ex:
            if self.autocommit:
                self.rollback()
            raise ex
        else:
            if self.autocommit:
                self.commit()
