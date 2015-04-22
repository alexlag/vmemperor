var Reflux = require('reflux'),
    VMAPI = require('../api/vmemp-api');

PoolActions = Reflux.createActions({
  'list': { asyncResult: true }
});

PoolActions.list.listenAndPromise( VMAPI.pool.list );

module.exports = PoolActions;