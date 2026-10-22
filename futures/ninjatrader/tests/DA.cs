namespace System.ComponentModel.DataAnnotations {
  [System.AttributeUsage(System.AttributeTargets.Property)] public class RangeAttribute : System.Attribute { public RangeAttribute(double a, double b) { } public RangeAttribute(int a, int b) { } }
  [System.AttributeUsage(System.AttributeTargets.Property)] public class DisplayAttribute : System.Attribute { public string Name; public int Order; public string GroupName; }
}
