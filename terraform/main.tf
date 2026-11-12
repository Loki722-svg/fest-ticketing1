# Infrastructure as Code: one small cloud VM that runs the Docker Compose stack,
# plus a storage bucket for event images. Written for AWS; swap the provider
# if your college gives you Azure/GCP credits.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  default = "ap-south-1"
}
variable "key_name" {
  description = "Existing EC2 key pair name"
}
variable "bucket_name" {
  description = "Globally unique bucket name for event images"
}
variable "instance_type" {
  default = "t3.micro"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-22.04-amd64-server-*"]
  }
}

resource "aws_security_group" "fest" {
  name        = "fest-ticketing-sg"
  description = "Allow SSH and web"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.fest.id]

  user_data = <<-EOT
    #!/bin/bash
    apt-get update -y
    apt-get install -y docker.io docker-compose-v2 git
    systemctl enable --now docker
  EOT

  tags = {
    Name = "fest-ticketing"
  }
}

resource "aws_s3_bucket" "images" {
  bucket = var.bucket_name
}

output "app_url" {
  value = "http://${aws_instance.app.public_ip}:8080"
}
