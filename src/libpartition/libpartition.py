from kazoo.client import KazooClient
import gevent
from gevent import Greenlet
from consistent_hash import ConsistentHash
import logging

""" Partition Library 
This library provides functionality to implement partition sharing between
cluster nodes
"""

class PartitionClient(object):
    """ Client Class for the Partition Library
    Example usage:
    ---------------------
    import libpartition
    from libpartition import PartitionClient

    def own_change_cb(l):
            print "ownership change:" + str(l)

    c = PartitionClient("test", "s1", ["s1", "s2", "s3"], 32, 
            own_change_cb, "zookeeper_s1")

    ##do some real work now"
    if (c.own_partition(1)):
        ...... do something with partition #1 .....
        .........
    ...
    c.update_cluster_list(["s1", "s2"])
    ...
    ----------------------
    You should not call any partition library routine from within the 
    callback function

    Args:
        app_name(str): Name of the app for which partition cluster is used
        self_name(str): Name of the local cluster node (can be ip address)
        cluster_list(list): List of all the nodes in the cluster including 
            local node
        max_partition(int): Partition space always go from 0..max_partition-1
        partition_update_cb: Callback function invoked when partition
            ownership list is updated.x
        zk_server(str): <zookeeper server>:<zookeeper server port>
    """
    def __init__(
            self, app_name, self_name, cluster_list, max_partition,
            partition_update_cb, zk_server):
       
        # Initialize local variables
        self._zk_server = zk_server
        self._cluster_list = set(cluster_list)
        self._max_partition = max_partition
        self._update_cb = partition_update_cb
        self._curr_part_ownership_list = []
        self._target_part_ownership_list = []
        self._con_hash = ConsistentHash(cluster_list)
        self._name = self_name

        # some sanity check
        if not(self._name in cluster_list):
            raise ValueError('cluster list is missing local server name')

        # connect to zookeeper
        self._zk = KazooClient(zk_server)
        self._zk.start()

        # create a lock array to contain locks for each partition
        self._part_locks = []
        for part in range(0, self._max_partition):
            lockpath = "/lockpath/"+ app_name + "/" + str(part)
            l = self._zk.Lock(lockpath, self._name)
            self._part_locks.append(l)

        # initialize partition # to lock acquire greenlet dictionary
        self._part_lock_task_dict = {}

        # update target partition ownership list
        for part in range(0, self._max_partition):
            if (self._con_hash.get_node(str(part)) == self._name):
                self._target_part_ownership_list.append(part)

        # update current ownership list
        self._acquire_partition_ownership()

    #end __init__

    # following routine is the greenlet task function to acquire the lock
    # for a partition
    def _acquire_lock(self, part):
        # lock for the partition
        l = self._part_locks[part]

        while True:
            if (l.cancelled == True):
                # a lock acquisition is getting cancelled let's wait
                logging.info("lock acquisition is getting cancelled, \
                        lets wait")
                gevent.sleep(1)
            else:
                break

        # go in an infinite loop waiting to acquire the lock
        while True:
            ret = l.acquire(blocking=False)
            if ret == True:

                logging.info("Acquired lock for:" + str(part))
                self._curr_part_ownership_list.append(part)
                self._update_cb(self._curr_part_ownership_list)
                return ret
            else:
                gevent.sleep(1)
    #end _acquire_lock

    # get rid of finished spawned tasks from datastructures
    def _cleanup_greenlets(self):
        for part in self._part_lock_task_dict.keys():
            if (self._part_lock_task_dict[part].ready()):
                del self._part_lock_task_dict[part]
    #end _cleanup_greenlets 

    # following routine launches tasks to acquire partition locks
    def _acquire_partition_ownership(self):
        # cleanup any finished greenlets
        self._cleanup_greenlets()

        # this variable will help us decide if we need to call callback
        updated_curr_ownership = False 

        for part in range(0, self._max_partition):
            if (part in self._target_part_ownership_list):
                if (part in self._curr_part_ownership_list):
                    # do nothing, I already have ownership of this partition
                    logging.info("No need to acquire ownership of:" +
                            str(part))
                else:
                    # I need to acquire lock for this partition before I own
                    if (part in self._part_lock_task_dict.keys()):
                        # do nothing there is already a greenlet running to
                        # acquire the lock
                        logging.info("Already a greenlet running to" 
                                " acquire:" + str(part))
                    else:
                        # launch the greenlet to acquire the loc, k
                        g = Greenlet.spawn(self._acquire_lock, part)
                        self._part_lock_task_dict[part] = g

            else:
                # give up ownership of the partition

                # cancel any lock acquisition which is ongoing 
                if (part in self._part_lock_task_dict.keys()):
                    # kill the greenlet trying to get the lock for this
                    # partition
                    self._part_lock_task_dict[part].kill()
                    del self._part_lock_task_dict[part]

                    logging.info("canceling lock acquisition going on \
                            for:" + str(part))
                    try:
                        self._part_locks[part].cancel()
                    except:
                        pass

                if (part in self._curr_part_ownership_list):
                    # release if lock was already acquired
                    logging.info("release the lock which was acquired:" + \
                            str(part))
                    try:
                        self._part_locks[part].release()
                    except:
                        pass
                    
                    self._curr_part_ownership_list.remove(part)
                    updated_curr_ownership = True
                    logging.info("gave up ownership of:" + str(part))

        if (updated_curr_ownership is True):
            # current partition membership was updated call the callback 
            self._update_cb(self._curr_part_ownership_list)
        
    #end _acquire_partition_ownership

    def update_cluster_list(self, cluster_list):
        """ Updates the cluster node list
        Args:
            cluster_list(list): New list of names of the nodes in 
                the cluster
        Returns:
            None
        """
        # some sanity check
        if not(self._name in cluster_list):
            raise ValueError('cluster list is missing local server name')

        new_cluster_list = set(cluster_list)
        new_servers = list(new_cluster_list.difference(
            self._cluster_list))
        deleted_servers = list(set(self._cluster_list).difference(
            new_cluster_list)) 
        self._cluster_list = cluster_list
        logging.info("deleted servers:" + str(deleted_servers))
        logging.info("new servers:" + str(new_servers))

        # update the hash structure
        if new_servers:
            self._con_hash.add_nodes(new_servers)
        if deleted_servers:
            self._con_hash.del_nodes(deleted_servers)

        # update target partition ownership list
        self._target_part_ownership_list = []
        for part in range(0, self._max_partition):
            if (self._con_hash.get_node(str(part)) == self._name):
                if not (part in self._target_part_ownership_list):
                    self._target_part_ownership_list.append(part)

        # update current ownership list
        self._acquire_partition_ownership()

    #end update_cluster_list

    def own_partition(self, part_no):
        """ Returns ownership information of a partition
        Args:
            part_no(int) : Partition no 
        Returns:
            True if partition is owned by the local node
            False if partition is not owned by the local node
        """
        return part_no in self._curr_part_ownership_list 
    #end own_partition

    def close(self):
        """ Closes any connections and frees up any data structures
        Args:
        Returns:
            None
        """
        # clean up greenlets
        for part in self._part_lock_task_dict.keys():
            try:
                self._part_lock_task_dict[part].kill()
            except:
                pass

        # close zookeeper
        try:
            self._zk.stop()
        except:
            pass
        try:
            self._zk.close()
        except:
            pass

    #end close
