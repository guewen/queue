# Copyright 2016 Camptocamp
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import inspect
import logging

from odoo import models, api
from ..job import DelayableRecordset
from ..delay import Delayable

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    """The base model, which is implicitly inherited by all models.

    A new :meth:`~with_delay` method is added on all Odoo Models, allowing to
    postpone the execution of a job method in an asynchronous process.
    """
    _inherit = 'base'

    @api.model_cr
    def _register_hook(self):
        """Register marked jobs"""
        super(Base, self)._register_hook()
        job_methods = [
            method for __, method
            in inspect.getmembers(self.__class__, predicate=inspect.isfunction)
            if getattr(method, 'delayable', None)
        ]
        for job_method in job_methods:
            self.env['queue.job.function']._register_job(self, job_method)

    @api.multi
    def with_delay(self, priority=None, eta=None,
                   max_retries=None, description=None,
                   channel=None, identity_key=None):
        """Return a ``DelayableRecordset``

        It is a shortcut for the longer form as shown below::

            self.with_delay(priority=20).action_done()
            # is equivalent to:
            self.delayable().set(priority=20).action_done().delay()

        When using :meth:``with_delay``, the final ``delay()`` is implicit.
        See the documentation of :meth:``delayable`` for more details.
        """
        return DelayableRecordset(self, priority=priority,
                                  eta=eta,
                                  max_retries=max_retries,
                                  description=description,
                                  channel=channel,
                                  identity_key=identity_key)

    @api.multi
    def delayable(self, priority=None, eta=None,
                  max_retries=None, description=None,
                  channel=None, identity_key=None):
        """Return a ``Delayable``

        The returned instance allow to enqueue any method of the recordset's
        Model which is decorated by :func:`~odoo.addons.queue_job.job.job`.

        Usage::

            delayable = self.env['res.users'].browse(10).delayable(priority=20)
            delayable.do_work({'name': 'test'}).delay()


        In the line above, ``do_work`` is allowed to be delayed because the
        method definition of the fictive method ``do_work`` is decorated by
        ``@job``. The ``do_work`` method will to be executed directly. It will
        be executed in an asynchronous job.

        Method calls on a Delayable generally return themselves, so calls can
        be chained together::

            delayable.set(priority=15).do_work({'name': 'test'}).delay()

        The order of the calls that build the job is not relevant, beside
        the call to ``delay()`` that must happen at the very end. This is
        equivalent to the one before::

            delayable.do_work({'name': 'test'}).set(priority=15).delay()

        Very importantly, ``delay()`` must be called on the top-most parent
        of a chain of jobs, so if you have this::

            job1 = record1.delayable().do_work()
            job2 = record2.delayable().do_work()
            job1.done(job2)

        The ``delay()`` call must be made on ``job1``, otherwise ``job2`` will
        be delayed, but ``job1`` will never be. When done on ``job1``, the
        ``delay()`` call will traverse the graph of jobs and delay all of
        them::

            job1.delay()

        For more details on the graph dependencies, read the documentation of
        :module:`~odoo.addons.queue_job.delay`.

        :param priority: Priority of the job, 0 being the higher priority.
                         Default is 10.
        :param eta: Estimated Time of Arrival of the job. It will not be
                    executed before this date/time.
        :param max_retries: maximum number of retries before giving up and set
                            the job state to 'failed'. A value of 0 means
                            infinite retries.  Default is 5.
        :param description: human description of the job. If None, description
                            is computed from the function doc or name
        :param channel: the complete name of the channel to use to process
                        the function. If specified it overrides the one
                        defined on the function
        :param identity_key: key uniquely identifying the job, if specified
                             and a job with the same key has not yet been run,
                             the new job will not be added.
        :return: instance of a Delayable
        :rtype: :class:`odoo.addons.queue_job.job.Delayable`

        Note for developers: if you want to run tests or simply disable
        jobs queueing for debugging purposes, you can:

            a. set the env var `TEST_QUEUE_JOB_NO_DELAY=1`
            b. pass a ctx key `test_queue_job_no_delay=1`

        In tests you'll have to mute the logger like:

            @mute_logger('odoo.addons.queue_job.models.base')
        """
        return Delayable(self, priority=priority,
                         eta=eta,
                         max_retries=max_retries,
                         description=description,
                         channel=channel,
                         identity_key=identity_key)
