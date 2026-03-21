terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.273.0  " # Ultima ver according to https://registry.terraform.io/providers/aliyun/alicloud/latest
    }
  }
}

provider "alicloud" {
  region = "na-south-1"
  skip_region_validation = true # México
}

# 1. Data Source para Zonas (Faltaba en tu código)
data "alicloud_zones" "default" {
  available_resource_creation = "VSwitch"
}

# 2. Data Source para Imagen (Mejor práctica que hardcodear el ID)
# Busca automáticamente Ubuntu 22.04 oficial en la región
data "alicloud_images" "ubuntu" {
  name_regex  = "^ubuntu_22_04_x64_.*"
  owners      = "system"
  most_recent = true
}

# VPC
resource "alicloud_vpc" "vpc" {
  vpc_name   = "${var.name}-vpc"
  cidr_block = "172.16.0.0/16"
}

# VSwitch
resource "alicloud_vswitch" "vswitch" {
  vpc_id       = alicloud_vpc.vpc.id
  cidr_block   = "172.16.0.0/24"
  zone_id      = data.alicloud_zones.default.zones[0].id
  vswitch_name = "${var.name}-vswitch"
}

# Security Group
resource "alicloud_security_group" "group" {
  security_group_name = "${var.name}-sg"
  description = "Security group para ${var.name}"
  vpc_id      = alicloud_vpc.vpc.id
}

# Regla de Seguridad (SSH) - CRÍTICO: Sin esto no puedes conectarte
resource "alicloud_security_group_rule" "allow_app" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "8000/8000"
  cidr_ip    = "0.0.0.0/0"
  security_group_id = alicloud_security_group.group.id
}


# Instancia ECS
resource "alicloud_instance" "instance" {
  availability_zone = data.alicloud_zones.default.zones[0].id
  
  # Instancia
  instance_type     = "ecs.c9i.large"
  
  security_groups   = [alicloud_security_group.group.id]
  
  # Disco del sistema (también actualizado)
  system_disk_category    = "cloud_essd"
  system_disk_name        = "${var.name}-system-disk"
  system_disk_description = "Disco sistema ${var.name}"
  
  # Usamos la imagen encontrada por el data source
  image_id        = data.alicloud_images.ubuntu.images[0].id
  
  instance_name   = var.name
  vswitch_id      = alicloud_vswitch.vswitch.id
  
  # Configuración de Internet
  internet_max_bandwidth_out = 10
  internet_charge_type       = "PayByBandwidth"

  data_disks {
    name        = "${var.name}-data-disk"
    size        = 20
    category  = "cloud_essd"         
    description = "Disco de datos"
    delete_with_instance = true         # Se borra al destruir la instancia
  }
}
resource "alicloud_security_group_rule" "allow_ssh" {
  type              = "ingress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "22/22"
  cidr_ip           = "0.0.0.0/0"
  security_group_id = alicloud_security_group.group.id
}
