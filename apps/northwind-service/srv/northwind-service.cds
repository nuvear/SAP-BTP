using { northwind as db } from '../db/schema';

// Read-only data service. It stands in for a released SAP API.
//
// THE ROW RULE LIVES HERE, AND ONLY HERE.
//   SalesHQ      sees every order.
//   SalesRegion  sees only orders whose salesperson works in the user's own country
//                (user attribute "country": USA = Seattle office, UK = London office).
// The MCP server forwards the user's identity and does not repeat this rule.
@path    : '/odata/v4/northwind'
@requires: 'authenticated-user'
service NorthwindService {

  @readonly
  @restrict: [
    { grant: 'READ', to: 'SalesHQ' },
    { grant: 'READ', to: 'SalesRegion', where: 'Employee.Country = $user.country' }
  ]
  entity Orders       as projection on db.Orders;

  // Order lines are reachable through Orders, and carry the same rule.
  @readonly
  @restrict: [
    { grant: 'READ', to: 'SalesHQ' },
    { grant: 'READ', to: 'SalesRegion', where: 'order.Employee.Country = $user.country' }
  ]
  entity OrderDetails as projection on db.OrderDetails;

  // Reference data: every signed-in sales user may read it.
  @readonly @restrict: [{ grant: 'READ', to: ['SalesHQ', 'SalesRegion'] }]
  entity Products     as projection on db.Products;
  @readonly @restrict: [{ grant: 'READ', to: ['SalesHQ', 'SalesRegion'] }]
  entity Suppliers    as projection on db.Suppliers;
  @readonly @restrict: [{ grant: 'READ', to: ['SalesHQ', 'SalesRegion'] }]
  entity Categories   as projection on db.Categories;
  @readonly @restrict: [{ grant: 'READ', to: ['SalesHQ', 'SalesRegion'] }]
  entity Shippers     as projection on db.Shippers;
  @readonly @restrict: [{ grant: 'READ', to: ['SalesHQ', 'SalesRegion'] }]
  entity Customers    as projection on db.Customers;
  @readonly @restrict: [{ grant: 'READ', to: ['SalesHQ', 'SalesRegion'] }]
  entity Employees    as projection on db.Employees;
}
