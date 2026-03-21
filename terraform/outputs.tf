output "instance_public_ip" {
  description = "IP pública de la instancia ECS"
  value       = alicloud_instance.instance.public_ip
}

output "instance_id" {
  description = "ID de la instancia ECS"
  value       = alicloud_instance.instance.id
}