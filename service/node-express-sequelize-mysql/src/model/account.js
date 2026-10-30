const { Model, QueryTypes } = require('sequelize');
const { BINARYUUID,VIRTUALBINARYUUID,fromBinaryUUID } = require("@hypercharlie/sequelize-binary-uuid");

module.exports = (sequelize, DataTypes) => {
  class Account extends Model {
    /**
     * Helper method for defining associations.
     * This method is not a part of Sequelize lifecycle.
     * The `models/index` file will call this method automatically.
     */
    static associate(models) {
      // define association here
      Account.hasMany(models.list, {
        foreignKey: 'accountId',
      });
    }
    
    static statistics() {
      return sequelize.query(`select id AS account_id, login AS account_login, count(list_id) AS list_count, round(avg(nb_tasks),2) AS task_avg from (select account.id, account.login, list.id list_id, count(task.id) nb_tasks from account inner join list on (list.account_id=account.id) left join task on (task.list_id=list.id) group by account.id, account.login, list.id) t group by id, login`, {
        type: QueryTypes.SELECT,
      }).then(rows => rows.map(row => ({ ...row, account_id: fromBinaryUUID(row.account_id) })));
    }
  }

  Account.init({
    bid: BINARYUUID({
      field: 'id',
      primaryKey: true,
      allowNull: false
    }),
    id: VIRTUALBINARYUUID("bid", "id"),
    login: {
      allowNull: true,
      type: DataTypes.TEXT,
      unique: true,
    },
  }, {
    sequelize,
    tableName: 'account',
    createdAt: 'creationDate',
    updatedAt: false,
    underscored: true,
    modelName: 'account',
  });

  return Account;
};
