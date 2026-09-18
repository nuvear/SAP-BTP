// Northwind data model for the course.
// Fictional sample data (Microsoft's Northwind). All dates are shifted forward by 28 years.
namespace northwind;

entity Categories {
  key CategoryID   : Integer;
      CategoryName : String(40);
      Description  : String(200);
}

entity Suppliers {
  key SupplierID   : Integer;
      CompanyName  : String(60);
      ContactName  : String(60);
      ContactTitle : String(60);
      City         : String(40);
      Country      : String(40);   // decides the standard lead time (policy NW-POL-005)
}

entity Shippers {
  key ShipperID   : Integer;       // 1 Speedy Express, 2 United Package, 3 Federal Shipping
      CompanyName : String(40);
}

entity Customers {
  key CustomerID   : String(5);
      CompanyName  : String(60);
      ContactName  : String(60);
      ContactTitle : String(60);
      City         : String(40);
      Country      : String(40);
}

entity Employees {
  key EmployeeID : Integer;
      LastName   : String(40);
      FirstName  : String(40);
      Title      : String(60);
      ReportsTo  : Association to Employees;
      City       : String(40);
      Country    : String(40);     // USA = Seattle office, UK = London office. Used by the row rule.
}

entity Products {
  key ProductID    : Integer;
      ProductName  : String(60);
      Supplier     : Association to Suppliers;
      Category     : Association to Categories;
      UnitPrice    : Decimal(10, 2);
      UnitsInStock : Integer;
      UnitsOnOrder : Integer;
      ReorderLevel : Integer;
      Discontinued : Boolean;
}

entity Orders {
  key OrderID      : Integer;
      Customer     : Association to Customers;
      Employee     : Association to Employees;   // the salesperson on the order
      OrderDate    : Date;
      RequiredDate : Date;
      ShippedDate  : Date;                       // empty = not shipped yet
      ShipVia      : Association to Shippers;
      Freight      : Decimal(10, 2);
      ShipName     : String(60);
      ShipCity     : String(40);
      ShipCountry  : String(40);
      details      : Composition of many OrderDetails
                       on details.order = $self;
}

entity OrderDetails {
  key order     : Association to Orders;
  key product   : Association to Products;
      UnitPrice : Decimal(10, 2);
      Quantity  : Integer;
      Discount  : Decimal(4, 2);                 // fraction: 0.15 = 15 percent
}
